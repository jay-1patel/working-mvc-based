"""Tenant distributor directory — dual SQLite / Mongo backend."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from .core import get_db_context, use_mongodb


def _deserialize(row) -> dict:
    d = dict(row)
    raw = d.get("product_interests", "[]")
    if isinstance(raw, str):
        try:
            d["product_interests"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            d["product_interests"] = []
    return d


def list_distributors(
    tenant_id: str,
    *,
    q: str = "",
    region: str = "",
    tier: str = "",
) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        flt: dict[str, Any] = {"tenant_id": tenant_id}
        if region:
            flt["region"] = region
        if tier:
            flt["tier"] = tier
        rows = Repository("distributors").find_all(flt, sort=[("name", 1)])
        if q:
            like = q.lower()
            rows = [
                r for r in rows
                if like in str(r.get("wa_id") or "").lower()
                or like in str(r.get("name") or "").lower()
                or like in str(r.get("phone") or "").lower()
                or like in str(r.get("email") or "").lower()
            ]
        return [_deserialize(r) for r in rows]

    with get_db_context() as conn:
        clauses, params = ["tenant_id = ?"], [tenant_id]
        if q:
            clauses.append("(wa_id LIKE ? OR name LIKE ? OR phone LIKE ? OR email LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like, like, like])
        if region:
            clauses.append("region = ?")
            params.append(region)
        if tier:
            clauses.append("tier = ?")
            params.append(tier)
        rows = conn.execute(
            f"SELECT * FROM distributors WHERE {' AND '.join(clauses)} "
            "ORDER BY name COLLATE NOCASE ASC",
            params,
        ).fetchall()
        return [_deserialize(r) for r in rows]


def count_distributors(
    tenant_id: str,
    *,
    region: str = "",
    tier: str = "",
    product_interest: str = "",
) -> int:
    if use_mongodb():
        from .mongo import Repository

        flt: dict[str, Any] = {"tenant_id": tenant_id}
        if region:
            flt["region"] = region
        if tier:
            flt["tier"] = tier
        rows = Repository("distributors").find_all(flt)
        if product_interest:
            needle = product_interest.lower()
            rows = [r for r in rows if needle in str(r.get("product_interests") or "").lower()]
        return len(rows)

    with get_db_context() as conn:
        clauses, params = ["tenant_id = ?"], [tenant_id]
        if region:
            clauses.append("region = ?")
            params.append(region)
        if tier:
            clauses.append("tier = ?")
            params.append(tier)
        if product_interest:
            clauses.append("product_interests LIKE ?")
            params.append(f"%{product_interest}%")
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM distributors WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        return int(row["cnt"]) if row else 0


def get_distributor(tenant_id: str, wa_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("distributors").find_one({"tenant_id": tenant_id, "wa_id": wa_id})
        return _deserialize(row) if row else None
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM distributors WHERE wa_id = ? AND tenant_id = ?",
            (wa_id, tenant_id),
        ).fetchone()
        return _deserialize(row) if row else None


def distributor_exists_globally(wa_id: str) -> bool:
    if use_mongodb():
        from .mongo import Repository

        return Repository("distributors").find_one({"wa_id": wa_id}) is not None
    with get_db_context() as conn:
        return conn.execute("SELECT 1 FROM distributors WHERE wa_id = ?", (wa_id,)).fetchone() is not None


def get_distributor_by_wa_id(wa_id: str) -> Optional[dict]:
    """Lookup distributor by WhatsApp id (legacy paths without tenant scoping)."""
    if use_mongodb():
        from .mongo import Repository

        row = Repository("distributors").find_one({"wa_id": wa_id})
        return _deserialize(row) if row else None
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM distributors WHERE wa_id = ? LIMIT 1",
            (wa_id,),
        ).fetchone()
        return _deserialize(row) if row else None


def insert_distributor(tenant_id: str, body) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "wa_id": body.wa_id.strip(),
        "tenant_id": tenant_id,
        "name": body.name,
        "phone": body.phone,
        "email": body.email,
        "region": body.region,
        "city": body.city,
        "address": body.address,
        "service_area": body.service_area,
        "tier": body.tier,
        "product_interests": json.dumps(body.product_interests),
        "sales_volume": body.sales_volume,
        "last_order_value": body.last_order_value,
        "outstanding_payments": body.outstanding_payments,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    if use_mongodb():
        from .mongo import Repository

        Repository("distributors").insert(payload)
        return
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO distributors
                (wa_id, tenant_id, name, phone, email, region, city, address, service_area,
                 tier, product_interests, sales_volume, last_order_value, outstanding_payments,
                 notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["wa_id"],
                tenant_id,
                body.name,
                body.phone,
                body.email,
                body.region,
                body.city,
                body.address,
                body.service_area,
                body.tier,
                payload["product_interests"],
                body.sales_volume,
                body.last_order_value,
                body.outstanding_payments,
                body.notes,
                now,
                now,
            ),
        )


def update_distributor(tenant_id: str, wa_id: str, updates: dict) -> tuple[dict, dict]:
    """Apply partial update; returns (before_row, changes dict). Raises LookupError if missing."""
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("distributors")
        before = repo.find_one({"tenant_id": tenant_id, "wa_id": wa_id})
        if not before:
            raise LookupError(wa_id)
        patch = dict(updates)
        if "product_interests" in patch:
            patch["product_interests"] = json.dumps(patch["product_interests"])
        patch["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        repo.update({"tenant_id": tenant_id, "wa_id": wa_id}, patch)
        changes = {}
        for k in ("name", "phone", "email", "region", "tier"):
            if k in updates and updates[k] is not None and before.get(k) != updates[k]:
                changes[k] = {"before": before.get(k), "after": updates[k]}
        return dict(before), changes

    fields, values = [], []
    for field, value in updates.items():
        if field == "product_interests":
            value = json.dumps(value)
        fields.append(f"{field} = ?")
        values.append(value)
    fields.append("updated_at = ?")
    values.append(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    values.extend([wa_id, tenant_id])
    with get_db_context() as conn:
        before = conn.execute(
            "SELECT name, phone, email, region, tier FROM distributors WHERE wa_id = ? AND tenant_id = ?",
            (wa_id, tenant_id),
        ).fetchone()
        result = conn.execute(
            f"UPDATE distributors SET {', '.join(fields)} WHERE wa_id = ? AND tenant_id = ?",
            values,
        )
        if result.rowcount == 0:
            raise LookupError(wa_id)
        changes = {}
        if before:
            for k in ("name", "phone", "email", "region", "tier"):
                if k in updates and updates[k] is not None and before[k] != updates[k]:
                    changes[k] = {"before": before[k], "after": updates[k]}
        return dict(before or {}), changes


def delete_distributor(tenant_id: str, wa_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("distributors")
        row = repo.find_one({"tenant_id": tenant_id, "wa_id": wa_id})
        if not row:
            return None
        repo.delete_one({"tenant_id": tenant_id, "wa_id": wa_id})
        return dict(row)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT name, phone, region FROM distributors WHERE wa_id = ? AND tenant_id = ?",
            (wa_id, tenant_id),
        ).fetchone()
        result = conn.execute(
            "DELETE FROM distributors WHERE wa_id = ? AND tenant_id = ?",
            (wa_id, tenant_id),
        )
        if result.rowcount == 0:
            return None
        return dict(row) if row else {}