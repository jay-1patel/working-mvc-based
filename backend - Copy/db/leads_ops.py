"""Leads inbox queries — dual SQLite / Mongo backend."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .core import get_db, get_db_context, use_mongodb

LEAD_STATUSES = ("new", "contacted", "qualified", "won", "lost", "closed")


def row_to_lead(row) -> dict:
    d = dict(row)
    collected = d.get("collected")
    if isinstance(collected, str):
        try:
            d["collected"] = json.loads(collected or "{}")
        except (json.JSONDecodeError, TypeError):
            d["collected"] = {}
    elif not isinstance(collected, dict):
        d["collected"] = {}
    return d


def _mongo_filters(
    tenant_id: Optional[str],
    status: Optional[str],
    assignee: Optional[str],
    q: Optional[str],
) -> dict[str, Any]:
    flt: dict[str, Any] = {}
    if tenant_id:
        flt["tenant_id"] = tenant_id.strip()
    if status:
        flt["status"] = status
    if assignee is not None:
        flt["assignee"] = assignee.strip()
    if q and q.strip():
        flt["$or"] = [
            {"wa_id": {"$regex": q.strip(), "$options": "i"}},
            {"user_name": {"$regex": q.strip(), "$options": "i"}},
            {"phone": {"$regex": q.strip(), "$options": "i"}},
            {"email": {"$regex": q.strip(), "$options": "i"}},
            {"collected": {"$regex": q.strip(), "$options": "i"}},
        ]
    return flt


def list_leads(
    *,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("leads")
        flt = _mongo_filters(tenant_id, status, assignee, q)
        total = repo.count(flt)
        rows = repo.find(flt, sort=[("created_at", -1), ("id", -1)], limit=limit, offset=offset)
        return {"total": total, "count": len(rows), "items": [row_to_lead(r) for r in rows]}

    where, params = " WHERE 1=1", []
    if tenant_id:
        where += " AND tenant_id = ?"
        params.append(tenant_id.strip())
    if status:
        where += " AND status = ?"
        params.append(status)
    if assignee is not None:
        where += " AND assignee = ?"
        params.append(assignee.strip())
    if q:
        like = f"%{q.strip()}%"
        where += " AND (wa_id LIKE ? OR user_name LIKE ? OR phone LIKE ? OR email LIKE ? OR collected LIKE ?)"
        params.extend([like, like, like, like, like])
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM leads" + where, params).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM leads" + where + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return {"total": total, "count": len(rows), "items": [row_to_lead(r) for r in rows]}
    finally:
        conn.close()


def export_lead_rows(
    *,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
) -> list:
    if use_mongodb():
        from .mongo import Repository

        flt = _mongo_filters(tenant_id, status, assignee, None)
        rows = Repository("leads").find(
            flt, sort=[("created_at", -1), ("id", -1)], limit=None
        )
        return [row_to_lead(r) for r in rows]

    where, params = " WHERE 1=1", []
    if tenant_id:
        where += " AND tenant_id = ?"
        params.append(tenant_id.strip())
    if status:
        where += " AND status = ?"
        params.append(status)
    if assignee is not None:
        where += " AND assignee = ?"
        params.append(assignee.strip())
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, tenant_id, wa_id, user_name, phone, email, collected, "
            "status, assignee, source, flow, created_at, updated_at "
            "FROM leads" + where + " ORDER BY created_at DESC, id DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_lead(lead_id: int) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("leads").find_one({"id": lead_id})
        return row_to_lead(row) if row else None
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return row_to_lead(row) if row else None
    finally:
        conn.close()


def update_lead(lead_id: int, *, status: Optional[str] = None, assignee: Optional[str] = None) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("leads")
        row = repo.find_one({"id": lead_id})
        if not row:
            return None
        updates: dict = {"updated_at": datetime.now(timezone.utc)}
        if status is not None:
            updates["status"] = status
        if assignee is not None:
            updates["assignee"] = assignee.strip()
        repo.update({"id": lead_id}, updates)
        return row_to_lead(repo.find_one({"id": lead_id}))

    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            return None
        if status is not None:
            conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
        if assignee is not None:
            conn.execute("UPDATE leads SET assignee = ? WHERE id = ?", (assignee.strip(), lead_id))
        conn.execute("UPDATE leads SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return row_to_lead(row) if row else None
    finally:
        conn.close()


def insert_lead_record(payload: dict) -> int:
    """Insert one lead row from flow runner / webhooks. Returns new lead id."""
    now = datetime.now(timezone.utc)
    if use_mongodb():
        from .mongo import Repository

        doc = dict(payload)
        doc.setdefault("status", "new")
        doc["created_at"] = doc.get("created_at") or now
        doc["updated_at"] = doc.get("updated_at") or now
        row = Repository("leads").insert(doc)
        return int(row["id"])

    cols = list(payload.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    with get_db_context() as conn:
        cur = conn.execute(
            f"INSERT INTO leads ({col_names}) VALUES ({placeholders})",
            [payload[c] for c in cols],
        )
        return int(cur.lastrowid)