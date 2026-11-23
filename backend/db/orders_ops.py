"""Admin order listing and mutation — dual SQLite / Mongo backend."""
from __future__ import annotations

import json
from typing import Any, Optional

from .core import get_db, get_db_context, use_mongodb


def _items_json(row: dict) -> dict:
    d = dict(row)
    raw = d.get("items", "[]")
    if isinstance(raw, str):
        try:
            d["items"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            d["items"] = []
    return d


def _sender_name(wa_id: str, conn=None) -> Optional[str]:
    if not wa_id:
        return None
    try:
        if use_mongodb():
            from .mongo import Repository

            rows = Repository("chat_history").find(
                {"wa_id": wa_id}, sort=[("id", -1)], limit=1
            )
            return rows[0].get("sender_name") if rows else None
        name_row = conn.execute(
            "SELECT sender_name FROM chat_history WHERE wa_id = ? ORDER BY id DESC LIMIT 1",
            (wa_id,),
        ).fetchone()
        return name_row["sender_name"] if name_row else None
    except Exception:
        return None


def order_to_dict(row, conn=None) -> dict:
    d = _items_json(row)
    if not d.get("customer_name"):
        d["customer_name"] = _sender_name(d.get("wa_id"), conn=conn)
    return d


def list_orders(
    *,
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    q: str = "",
    limit: int = 200,
) -> dict:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        flt: dict[str, Any] = {}
        if status:
            flt["status"] = status
        if order_type:
            flt["order_type"] = order_type
        if payment_status:
            flt["payment_status"] = payment_status
        rows = repo.find(flt, sort=[("id", -1)], limit=limit)
        if q.strip():
            like = q.strip().lower()

            def _match(r):
                for field in ("order_number", "wa_id", "customer_name", "customer_mobile"):
                    if like in str(r.get(field) or "").lower():
                        return True
                return False

            rows = [r for r in rows if _match(r)][:limit]
        orders = [order_to_dict(r) for r in rows]
        all_rows = repo.find_all({})
        counts = {
            "total": len(all_rows),
            "placed": sum(1 for r in all_rows if r.get("status") == "placed"),
            "delivered": sum(
                1 for r in all_rows if str(r.get("status") or "") in ("delivered", "completed")
            ),
            "cancelled": sum(1 for r in all_rows if r.get("status") == "cancelled"),
            "revenue": sum(
                float(r.get("total_amount") or 0)
                for r in all_rows
                if str(r.get("status") or "") not in ("cancelled", "returned")
            ),
        }
        return {"orders": orders, "count": len(orders), "counts": counts}

    conn = get_db()
    try:
        clauses = ["1=1"]
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if order_type:
            clauses.append("order_type = ?")
            params.append(order_type)
        if payment_status:
            clauses.append("payment_status = ?")
            params.append(payment_status)
        if q.strip():
            like = f"%{q.strip()}%"
            clauses.append(
                "(order_number LIKE ? OR wa_id LIKE ? "
                "OR customer_name LIKE ? OR customer_mobile LIKE ?)"
            )
            params.extend([like, like, like, like])
        sql = "SELECT * FROM orders WHERE " + " AND ".join(clauses) + " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        orders = [order_to_dict(r, conn=conn) for r in rows]
        counts = {
            "total": conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"] or 0,
            "placed": conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='placed'").fetchone()["c"] or 0,
            "delivered": conn.execute(
                "SELECT COUNT(*) AS c FROM orders WHERE status IN ('delivered','completed')"
            ).fetchone()["c"] or 0,
            "cancelled": conn.execute(
                "SELECT COUNT(*) AS c FROM orders WHERE status='cancelled'"
            ).fetchone()["c"] or 0,
            "revenue": conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) AS v FROM orders "
                "WHERE status NOT IN ('cancelled','returned')"
            ).fetchone()["v"] or 0,
        }
        return {"orders": orders, "count": len(orders), "counts": counts}
    finally:
        conn.close()


def order_stats() -> dict:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("orders").find_all({})
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in rows:
            by_status[str(r.get("status") or "")] = by_status.get(str(r.get("status") or ""), 0) + 1
            by_type[str(r.get("order_type") or "")] = by_type.get(str(r.get("order_type") or ""), 0) + 1
        return {
            "total": len(rows),
            "revenue": sum(float(r.get("total_amount") or 0) for r in rows),
            "placed": sum(1 for r in rows if r.get("status") == "placed"),
            "cancelled": sum(1 for r in rows if r.get("status") == "cancelled"),
            "delivered": sum(
                1 for r in rows if str(r.get("status") or "") in ("delivered", "completed")
            ),
            "by_status": by_status,
            "by_type": by_type,
        }

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(total_amount), 0) AS revenue, "
            "SUM(CASE WHEN status='placed' THEN 1 ELSE 0 END) AS placed, "
            "SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled, "
            "SUM(CASE WHEN status IN ('delivered','completed') THEN 1 ELSE 0 END) AS delivered "
            "FROM orders"
        ).fetchone()
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM orders GROUP BY status"
        ).fetchall()
        type_rows = conn.execute(
            "SELECT order_type, COUNT(*) AS c FROM orders GROUP BY order_type"
        ).fetchall()
        return {
            "total": row["total"] if row else 0,
            "revenue": row["revenue"] if row else 0,
            "placed": row["placed"] if row else 0,
            "cancelled": row["cancelled"] if row else 0,
            "delivered": row["delivered"] if row else 0,
            "by_status": {r["status"]: r["c"] for r in status_rows},
            "by_type": {r["order_type"]: r["c"] for r in type_rows},
        }
    finally:
        conn.close()


def get_order_record(order_id: str, conn=None) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        if str(order_id).isdigit():
            row = repo.find_one({"id": int(order_id)})
        else:
            row = repo.find_one({"order_number": order_id})
        if not row:
            row = repo.find_one({"id": order_id}) or repo.find_one({"order_number": str(order_id)})
        return order_to_dict(row) if row else None
    if conn is None:
        conn = get_db()
        close = True
    else:
        close = False
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ? OR order_number = ?",
            (order_id, order_id),
        ).fetchone()
        return order_to_dict(row, conn=conn) if row else None
    finally:
        if close:
            conn.close()


def update_order_record(order_id: str, updates: dict) -> Optional[int]:
    if not updates:
        return None
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        row = repo.find_one({"id": int(order_id)}) if str(order_id).isdigit() else None
        if row is None:
            row = repo.find_one({"order_number": order_id})
        if not row:
            row = repo.find_one({"id": order_id})
        if not row:
            return None
        repo.update({"id": row["id"]}, updates)
        return int(row["id"])
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id FROM orders WHERE id = ? OR order_number = ?",
            (order_id, order_id),
        ).fetchone()
        if not row:
            return None
        fields = []
        values: list = []
        for field, value in updates.items():
            fields.append(f"{field} = ?")
            values.append(value)
        conn.execute(
            f"UPDATE orders SET {', '.join(fields)} WHERE id = ?",
            values + [row["id"]],
        )
        return int(row["id"])


def delete_order_record(order_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        row = repo.find_one({"id": int(order_id)}) if str(order_id).isdigit() else None
        if row is None:
            row = repo.find_one({"order_number": order_id})
        if not row:
            return None
        repo.delete_one({"id": row["id"]})
        return dict(row)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id, order_number FROM orders WHERE id = ? OR order_number = ?",
            (order_id, order_id),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM orders WHERE id = ?", (row["id"],))
        return dict(row)