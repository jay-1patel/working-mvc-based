"""Customer directory aggregation — dual SQLite / Mongo."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .core import get_db, use_mongodb


def _parse_ts(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _wa_set_from_tables(tables: tuple[str, ...], tenant_id: Optional[str] = None) -> set[str]:
    if use_mongodb():
        from .mongo import Repository

        wa_ids: set[str] = set()
        flt = {"tenant_id": tenant_id} if tenant_id else {}
        for table in tables:
            for row in Repository(table).find_all(flt if flt else {}):
                wa = str(row.get("wa_id") or "").strip()
                if wa:
                    if tenant_id and table != "customers" and row.get("tenant_id") not in (None, "", tenant_id):
                        if str(row.get("tenant_id") or "") != str(tenant_id):
                            continue
                    wa_ids.add(wa)
        return wa_ids
    conn = get_db()
    try:
        if tenant_id:
            union_sql = """
                SELECT wa_id FROM orders WHERE tenant_id = ? AND wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM complaints WHERE tenant_id = ? AND wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM chat_history WHERE tenant_id = ? AND wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM user_states WHERE tenant_id = ? AND wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM customers WHERE tenant_id = ? AND wa_id IS NOT NULL AND wa_id != ''
            """
            params = (tenant_id,) * 5
        else:
            union_sql = """
                SELECT wa_id FROM orders WHERE wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM complaints WHERE wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM chat_history WHERE wa_id IS NOT NULL AND wa_id != ''
                UNION
                SELECT wa_id FROM user_states WHERE wa_id IS NOT NULL AND wa_id != ''
            """
            params = ()
        rows = conn.execute(union_sql, params).fetchall()
        return {str(r["wa_id"]) for r in rows if r["wa_id"]}
    finally:
        conn.close()


def _mongo_latest_field(table: str, wa_id: str, field: str, tenant_id: Optional[str] = None):
    from .mongo import Repository

    flt: dict[str, Any] = {"wa_id": wa_id}
    if tenant_id:
        flt["tenant_id"] = tenant_id
    rows = Repository(table).find(flt, sort=[("id", -1)], limit=50)
    for row in rows:
        val = row.get(field)
        if val not in (None, ""):
            return val
    return None


def _mongo_count(table: str, wa_id: str, extra: Optional[dict] = None, tenant_id: Optional[str] = None) -> int:
    from .mongo import Repository

    flt: dict[str, Any] = {"wa_id": wa_id}
    if tenant_id:
        flt["tenant_id"] = tenant_id
    if extra:
        flt.update(extra)
    return Repository(table).count(flt)


def _mongo_max_activity(wa_id: str, tenant_id: Optional[str] = None) -> Optional[str]:
    from .mongo import Repository

    stamps: list[str] = []
    flt: dict[str, Any] = {"wa_id": wa_id}
    if tenant_id:
        flt["tenant_id"] = tenant_id
    for table, field in (
        ("chat_history", "created_at"),
        ("orders", "created_at"),
        ("complaints", "created_at"),
        ("user_states", "updated_at"),
    ):
        for row in Repository(table).find(flt, sort=[(field, -1)], limit=1):
            ts = _parse_ts(row.get(field))
            if ts:
                stamps.append(ts)
    return max(stamps) if stamps else None


def build_global_customer(wa_id: str, conn=None) -> dict:
    if use_mongodb():
        name = (
            _mongo_latest_field("orders", wa_id, "customer_name")
            or _mongo_latest_field("chat_history", wa_id, "sender_name")
            or wa_id
        )
        mobile = _mongo_latest_field("orders", wa_id, "customer_mobile")
        order_count = _mongo_count("orders", wa_id)
        complaint_count = _mongo_count("complaints", wa_id)
        open_complaints = _mongo_count(
            "complaints",
            wa_id,
            extra={"status": {"$nin": ["resolved", "closed"]}},
        )
        spent = 0.0
        from .mongo import Repository

        for order in Repository("orders").find({"wa_id": wa_id}):
            if str(order.get("status") or "") not in ("cancelled", "returned"):
                spent += float(order.get("total_amount") or 0)
        return {
            "wa_id": wa_id,
            "name": name,
            "mobile": mobile,
            "total_orders": order_count,
            "total_complaints": complaint_count,
            "open_complaints": open_complaints,
            "total_spent": round(spent, 2),
            "last_active": _mongo_max_activity(wa_id),
        }

    order_name = conn.execute(
        """SELECT customer_name FROM orders
           WHERE wa_id=? AND customer_name IS NOT NULL AND customer_name != ''
           ORDER BY id DESC LIMIT 1""",
        (wa_id,),
    ).fetchone()
    sender_row = conn.execute(
        """SELECT sender_name FROM chat_history
           WHERE wa_id=? AND sender_name IS NOT NULL AND sender_name != ''
           ORDER BY id DESC LIMIT 1""",
        (wa_id,),
    ).fetchone()
    mobile_row = conn.execute(
        """SELECT customer_mobile FROM orders
           WHERE wa_id=? AND customer_mobile IS NOT NULL AND customer_mobile != ''
           ORDER BY id DESC LIMIT 1""",
        (wa_id,),
    ).fetchone()
    order_count = conn.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE wa_id=?", (wa_id,)
    ).fetchone()["c"] or 0
    complaint_count = conn.execute(
        "SELECT COUNT(*) AS c FROM complaints WHERE wa_id=?", (wa_id,)
    ).fetchone()["c"] or 0
    open_complaints = conn.execute(
        "SELECT COUNT(*) AS c FROM complaints WHERE wa_id=? AND status NOT IN ('resolved','closed')",
        (wa_id,),
    ).fetchone()["c"] or 0
    spent = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) AS v FROM orders
           WHERE wa_id=? AND status NOT IN ('cancelled','returned')""",
        (wa_id,),
    ).fetchone()["v"] or 0
    last_active = conn.execute(
        """SELECT MAX(last_seen) AS l FROM (
               SELECT MAX(created_at) AS last_seen FROM chat_history WHERE wa_id=?
               UNION ALL
               SELECT MAX(created_at) AS last_seen FROM orders WHERE wa_id=?
               UNION ALL
               SELECT MAX(created_at) AS last_seen FROM complaints WHERE wa_id=?
               UNION ALL
               SELECT MAX(updated_at) AS last_seen FROM user_states WHERE wa_id=?
           )""",
        (wa_id, wa_id, wa_id, wa_id),
    ).fetchone()["l"]
    return {
        "wa_id": wa_id,
        "name": (order_name["customer_name"] if order_name else None)
        or (sender_row["sender_name"] if sender_row else None)
        or wa_id,
        "mobile": mobile_row["customer_mobile"] if mobile_row else None,
        "total_orders": order_count,
        "total_complaints": complaint_count,
        "open_complaints": open_complaints,
        "total_spent": round(float(spent), 2),
        "last_active": last_active,
    }


def build_tenant_customer(wa_id: str, tenant_id: str, conn=None) -> dict:
    if use_mongodb():
        from .mongo import Repository

        cust = Repository("customers").find_one({"tenant_id": tenant_id, "wa_id": wa_id})
        order_name = _mongo_latest_field("orders", wa_id, "customer_name", tenant_id=tenant_id)
        sender_name = _mongo_latest_field("chat_history", wa_id, "sender_name", tenant_id=tenant_id)
        mobile = _mongo_latest_field("orders", wa_id, "customer_mobile", tenant_id=tenant_id)
        name = (
            (cust.get("name") if cust and cust.get("name") else None)
            or order_name
            or sender_name
            or wa_id
        )
        mobile_value = mobile or (cust.get("phone") if cust else None)
        order_count = _mongo_count("orders", wa_id, tenant_id=tenant_id)
        complaint_count = _mongo_count("complaints", wa_id, tenant_id=tenant_id)
        open_complaints = _mongo_count(
            "complaints",
            wa_id,
            tenant_id=tenant_id,
            extra={"status": {"$nin": ["resolved", "closed"]}},
        )
        spent = 0.0
        for order in Repository("orders").find({"tenant_id": tenant_id, "wa_id": wa_id}):
            if str(order.get("status") or "") not in ("cancelled", "returned"):
                spent += float(order.get("total_amount") or 0)
        return {
            "wa_id": wa_id,
            "name": name,
            "mobile": mobile_value,
            "email": (cust.get("email") if cust else None) or None,
            "city": (cust.get("city") if cust else None) or None,
            "state": (cust.get("state") if cust else None) or None,
            "company": (cust.get("company") if cust else None) or None,
            "language": (cust.get("language") if cust else None) or None,
            "message_count": (cust.get("message_count") if cust else None) or 0,
            "first_seen": (cust.get("first_seen") if cust else None) or None,
            "total_orders": order_count,
            "total_complaints": complaint_count,
            "open_complaints": open_complaints,
            "total_spent": round(spent, 2),
            "last_active": _mongo_max_activity(wa_id, tenant_id=tenant_id),
        }

    order_name = conn.execute(
        """SELECT customer_name FROM orders
           WHERE tenant_id = ? AND wa_id = ? AND customer_name IS NOT NULL AND customer_name != ''
           ORDER BY id DESC LIMIT 1""",
        (tenant_id, wa_id),
    ).fetchone()
    sender_name = conn.execute(
        """SELECT sender_name FROM chat_history
           WHERE tenant_id = ? AND wa_id = ? AND sender_name IS NOT NULL AND sender_name != ''
           ORDER BY id DESC LIMIT 1""",
        (tenant_id, wa_id),
    ).fetchone()
    mobile = conn.execute(
        """SELECT customer_mobile FROM orders
           WHERE tenant_id = ? AND wa_id = ? AND customer_mobile IS NOT NULL AND customer_mobile != ''
           ORDER BY id DESC LIMIT 1""",
        (tenant_id, wa_id),
    ).fetchone()
    cust = conn.execute(
        """SELECT name, phone, email, city, state, company, language,
                  message_count, first_seen
           FROM customers WHERE tenant_id = ? AND wa_id = ?""",
        (tenant_id, wa_id),
    ).fetchone()
    name = (
        (cust["name"] if cust and cust["name"] else None)
        or (order_name["customer_name"] if order_name else None)
        or (sender_name["sender_name"] if sender_name else None)
        or wa_id
    )
    mobile_value = (
        (mobile["customer_mobile"] if mobile else None)
        or (cust["phone"] if cust and cust["phone"] else None)
    )
    order_count = conn.execute(
        "SELECT COUNT(*) AS c FROM orders WHERE tenant_id = ? AND wa_id = ?",
        (tenant_id, wa_id),
    ).fetchone()["c"] or 0
    complaint_count = conn.execute(
        "SELECT COUNT(*) AS c FROM complaints WHERE tenant_id = ? AND wa_id = ?",
        (tenant_id, wa_id),
    ).fetchone()["c"] or 0
    open_complaints = conn.execute(
        """SELECT COUNT(*) AS c FROM complaints
           WHERE tenant_id = ? AND wa_id = ? AND status NOT IN ('resolved','closed')""",
        (tenant_id, wa_id),
    ).fetchone()["c"] or 0
    spent = conn.execute(
        """SELECT COALESCE(SUM(total_amount), 0) AS v FROM orders
           WHERE tenant_id = ? AND wa_id = ? AND status NOT IN ('cancelled','returned')""",
        (tenant_id, wa_id),
    ).fetchone()["v"] or 0
    last_active = conn.execute(
        """SELECT MAX(last_seen) AS l FROM (
               SELECT MAX(created_at) AS last_seen FROM chat_history WHERE tenant_id = ? AND wa_id = ?
               UNION ALL
               SELECT MAX(created_at) AS last_seen FROM orders WHERE tenant_id = ? AND wa_id = ?
               UNION ALL
               SELECT MAX(created_at) AS last_seen FROM complaints WHERE tenant_id = ? AND wa_id = ?
               UNION ALL
               SELECT MAX(updated_at) AS last_seen FROM user_states WHERE tenant_id = ? AND wa_id = ?
           )""",
        (tenant_id, wa_id, tenant_id, wa_id, tenant_id, wa_id, tenant_id, wa_id),
    ).fetchone()["l"]
    return {
        "wa_id": wa_id,
        "name": name,
        "mobile": mobile_value,
        "email": (cust["email"] if cust else None) or None,
        "city": (cust["city"] if cust else None) or None,
        "state": (cust["state"] if cust else None) or None,
        "company": (cust["company"] if cust else None) or None,
        "language": (cust["language"] if cust else None) or None,
        "message_count": (cust["message_count"] if cust else None) or 0,
        "first_seen": (cust["first_seen"] if cust else None) or None,
        "total_orders": order_count,
        "total_complaints": complaint_count,
        "open_complaints": open_complaints,
        "total_spent": round(float(spent), 2),
        "last_active": last_active,
    }


def list_global_customers(*, q: str = "", limit: int = 200) -> dict:
    tables = ("orders", "complaints", "chat_history", "user_states")
    wa_ids = sorted(_wa_set_from_tables(tables))
    needle = q.strip().lower()
    if needle:
        wa_ids = [w for w in wa_ids if needle in w.lower()]
    wa_ids = wa_ids[:limit]
    if use_mongodb():
        customers = [build_global_customer(w) for w in wa_ids]
    else:
        conn = get_db()
        try:
            customers = [build_global_customer(w, conn=conn) for w in wa_ids]
        finally:
            conn.close()
    customers.sort(key=lambda c: c.get("last_active") or "", reverse=True)
    return {"customers": customers, "count": len(customers)}


def list_tenant_customers(*, tenant_id: str, q: str = "", limit: int = 200) -> dict:
    tables = ("orders", "complaints", "chat_history", "user_states", "customers")
    wa_ids = sorted(_wa_set_from_tables(tables, tenant_id=tenant_id))
    needle = q.strip().lower()
    customers = []
    if use_mongodb():
        for wa_id in wa_ids:
            row = build_tenant_customer(wa_id, tenant_id)
            if needle and not any(
                needle in str(value or "").lower()
                for value in (wa_id, row.get("name"), row.get("mobile"))
            ):
                continue
            customers.append(row)
    else:
        conn = get_db()
        try:
            for wa_id in wa_ids:
                row = build_tenant_customer(wa_id, tenant_id, conn=conn)
                if needle and not any(
                    needle in str(value or "").lower()
                    for value in (wa_id, row.get("name"), row.get("mobile"))
                ):
                    continue
                customers.append(row)
        finally:
            conn.close()
    customers.sort(key=lambda c: c.get("last_active") or "", reverse=True)
    customers = customers[:limit]
    return {"customers": customers, "count": len(customers)}


def _since_days(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _row_in_window(created_at, days: int) -> bool:
    if created_at is None:
        return False
    if isinstance(created_at, datetime):
        dt = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    else:
        text = str(created_at).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text[:26])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                return False
    return dt >= _since_days(days)