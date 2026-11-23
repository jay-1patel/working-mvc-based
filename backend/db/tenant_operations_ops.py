"""Tenant-scoped customers and orders — dual SQLite / Mongo."""
from __future__ import annotations

import json
from typing import Any, Optional

from .core import get_db, get_db_context, use_mongodb
from .customer_agg import list_tenant_customers
from .orders_ops import order_to_dict


def tenant_list_customers(*, tenant_id: str, q: str = "", limit: int = 200) -> dict:
    return list_tenant_customers(tenant_id=tenant_id, q=q, limit=limit)


def tenant_export_customer_rows(tenant_id: str) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("customers").find(
            {"tenant_id": tenant_id},
            sort=[("last_seen", -1), ("id", -1)],
        )
        return [dict(r) for r in rows]
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT wa_id, name, phone, email, city, state, company, language,
                      message_count, first_seen, last_seen
               FROM customers WHERE tenant_id = ? ORDER BY last_seen DESC""",
            (tenant_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _tenant_order_counts(tenant_id: str, conn=None) -> dict:
    if use_mongodb():
        from .mongo import Repository

        rows = [r for r in Repository("orders").find_all({"tenant_id": tenant_id})]
        return {
            "total": len(rows),
            "placed": sum(1 for r in rows if r.get("status") == "placed"),
            "delivered": sum(
                1 for r in rows if str(r.get("status") or "") in ("delivered", "completed")
            ),
            "cancelled": sum(1 for r in rows if r.get("status") == "cancelled"),
            "revenue": sum(
                float(r.get("total_amount") or 0)
                for r in rows
                if str(r.get("status") or "") not in ("cancelled", "returned")
            ),
        }
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(CASE WHEN status='placed' THEN 1 ELSE 0 END), 0) AS placed,
                  COALESCE(SUM(CASE WHEN status IN ('delivered','completed') THEN 1 ELSE 0 END), 0) AS delivered,
                  COALESCE(SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END), 0) AS cancelled,
                  COALESCE(SUM(CASE WHEN status NOT IN ('cancelled','returned') THEN total_amount ELSE 0 END), 0) AS revenue
           FROM orders WHERE tenant_id = ?""",
        (tenant_id,),
    ).fetchone()
    return {
        "total": row["total"] or 0,
        "placed": row["placed"] or 0,
        "delivered": row["delivered"] or 0,
        "cancelled": row["cancelled"] or 0,
        "revenue": row["revenue"] or 0,
    }


def tenant_list_orders(
    *,
    tenant_id: str,
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    q: str = "",
    limit: int = 200,
) -> dict:
    if use_mongodb():
        from .mongo import Repository

        flt: dict[str, Any] = {"tenant_id": tenant_id}
        if status:
            flt["status"] = status
        if order_type:
            flt["order_type"] = order_type
        if payment_status:
            flt["payment_status"] = payment_status
        rows = Repository("orders").find(flt, sort=[("id", -1)], limit=limit)
        if q.strip():
            like = q.strip().lower()
            rows = [
                r for r in rows
                if any(like in str(r.get(field) or "").lower() for field in (
                    "order_number", "wa_id", "customer_name", "customer_mobile"
                ))
            ][:limit]
        orders = [order_to_dict(r) for r in rows]
        return {
            "orders": orders,
            "count": len(orders),
            "counts": _tenant_order_counts(tenant_id),
        }

    conn = get_db()
    try:
        clauses = ["tenant_id = ?"]
        params: list = [tenant_id]
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
                "(order_number LIKE ? OR wa_id LIKE ? OR customer_name LIKE ? OR customer_mobile LIKE ?)"
            )
            params.extend([like, like, like, like])
        rows = conn.execute(
            f"SELECT * FROM orders WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        orders = [order_to_dict(r, conn=conn) for r in rows]
        return {
            "orders": orders,
            "count": len(orders),
            "counts": _tenant_order_counts(tenant_id, conn=conn),
        }
    finally:
        conn.close()


def tenant_order_stats(tenant_id: str) -> dict:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("orders").find_all({"tenant_id": tenant_id})
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
            """SELECT COUNT(*) AS total, COALESCE(SUM(total_amount), 0) AS revenue,
                      SUM(CASE WHEN status='placed' THEN 1 ELSE 0 END) AS placed,
                      SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
                      SUM(CASE WHEN status IN ('delivered','completed') THEN 1 ELSE 0 END) AS delivered
               FROM orders WHERE tenant_id = ?""",
            (tenant_id,),
        ).fetchone()
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM orders WHERE tenant_id = ? GROUP BY status",
            (tenant_id,),
        ).fetchall()
        type_rows = conn.execute(
            "SELECT order_type, COUNT(*) AS c FROM orders WHERE tenant_id = ? GROUP BY order_type",
            (tenant_id,),
        ).fetchall()
        return {
            "total": row["total"] if row else 0,
            "revenue": row["revenue"] if row else 0,
            "placed": row["placed"] if row else 0,
            "cancelled": row["cancelled"] if row else 0,
            "delivered": row["delivered"] if row else 0,
            "by_status": {item["status"]: item["c"] for item in status_rows},
            "by_type": {item["order_type"]: item["c"] for item in type_rows},
        }
    finally:
        conn.close()


def tenant_get_order(tenant_id: str, order_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        flt = {"tenant_id": tenant_id}
        row = None
        if str(order_id).isdigit():
            row = repo.find_one({**flt, "id": int(order_id)})
        if row is None:
            row = repo.find_one({**flt, "order_number": order_id})
        return order_to_dict(row) if row else None

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND (id = ? OR order_number = ?)",
            (tenant_id, order_id, order_id),
        ).fetchone()
        return order_to_dict(row, conn=conn) if row else None
    finally:
        conn.close()


def tenant_update_order(tenant_id: str, order_id: str, updates: dict) -> Optional[dict]:
    if not updates:
        return None
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        row = repo.find_one({"tenant_id": tenant_id, "id": int(order_id)}) if str(order_id).isdigit() else None
        if row is None:
            row = repo.find_one({"tenant_id": tenant_id, "order_number": order_id})
        if not row:
            return None
        before = dict(row)
        repo.update({"id": row["id"]}, updates)
        return before

    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id, order_number, status, payment_status FROM orders WHERE tenant_id = ? AND (id = ? OR order_number = ?)",
            (tenant_id, order_id, order_id),
        ).fetchone()
        if not row:
            return None
        before = dict(row)
        fields, values = [], []
        for field, value in updates.items():
            fields.append(f"{field} = ?")
            values.append(value)
        conn.execute(
            f"UPDATE orders SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?",
            values + [row["id"], tenant_id],
        )
        return before


def tenant_delete_order(tenant_id: str, order_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("orders")
        row = repo.find_one({"tenant_id": tenant_id, "id": int(order_id)}) if str(order_id).isdigit() else None
        if row is None:
            row = repo.find_one({"tenant_id": tenant_id, "order_number": order_id})
        if not row:
            return None
        repo.delete_one({"id": row["id"]})
        return dict(row)

    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id, order_number, status, payment_status FROM orders WHERE tenant_id = ? AND (id = ? OR order_number = ?)",
            (tenant_id, order_id, order_id),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "DELETE FROM orders WHERE tenant_id = ? AND (id = ? OR order_number = ?)",
            (tenant_id, order_id, order_id),
        )
        return dict(row)