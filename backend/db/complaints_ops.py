"""Admin complaints API backing store — dual SQLite / Mongo."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .core import get_db, get_db_context, use_mongodb


def _enrich_complaint(item: dict, conn=None) -> dict:
    wa_id = item.get("wa_id")
    if conn is None and not use_mongodb():
        return item
    try:
        if use_mongodb():
            from .mongo import Repository

            chats = Repository("chat_history")
            name_rows = chats.find({"wa_id": wa_id}, sort=[("id", -1)], limit=1)
            item["name"] = (
                (name_rows[0].get("sender_name") if name_rows else None) or wa_id
            )
            user_rows = chats.find(
                {"wa_id": wa_id, "$or": [{"response": None}, {"response": ""}]},
                sort=[("id", -1)],
                limit=1,
            )
            item["last_user_message"] = (user_rows[0].get("message") if user_rows else None) or ""
        else:
            name_row = conn.execute(
                "SELECT sender_name FROM chat_history WHERE wa_id = ? ORDER BY id DESC LIMIT 1",
                (wa_id,),
            ).fetchone()
            item["name"] = (name_row["sender_name"] if name_row else None) or wa_id
            user_row = conn.execute(
                "SELECT message FROM chat_history "
                "WHERE wa_id = ? AND (response IS NULL OR response = '') "
                "ORDER BY id DESC LIMIT 1",
                (wa_id,),
            ).fetchone()
            item["last_user_message"] = (user_row["message"] if user_row else None) or ""
    except Exception:
        item.setdefault("name", wa_id)
        item.setdefault("last_user_message", "")
    return item


def list_complaints(*, status: Optional[str] = None, wa_id: Optional[str] = None, limit: int = 200) -> dict:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("complaints")
        flt: dict[str, Any] = {}
        if status:
            flt["status"] = status
        if wa_id:
            flt["wa_id"] = wa_id
        rows = repo.find(flt, sort=[("created_at", -1), ("id", -1)], limit=limit)
        complaints = [_enrich_complaint(dict(r)) for r in rows]
        open_count = repo.count({**flt, "status": "open"}) if not flt else repo.count({"status": "open"})
        return {"complaints": complaints, "count": len(complaints), "open_count": open_count}

    conn = get_db()
    try:
        sql = "SELECT * FROM complaints WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if wa_id:
            sql += " AND wa_id = ?"
            params.append(wa_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        complaints = [_enrich_complaint(dict(r), conn=conn) for r in rows]
        open_count = conn.execute(
            "SELECT COUNT(*) AS c FROM complaints WHERE status = 'open'"
        ).fetchone()["c"]
        return {"complaints": complaints, "count": len(complaints), "open_count": open_count or 0}
    finally:
        conn.close()


def get_complaint(ticket_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("complaints").find_one({"ticket_id": ticket_id})
        return dict(row) if row else None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM complaints WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_complaint(
    ticket_id: str,
    *,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    priority: Optional[str] = None,
) -> Optional[int]:
    now = datetime.utcnow().isoformat()
    updates: dict[str, Any] = {"updated_at": now}
    if status:
        updates["status"] = status
        if status in ("resolved", "closed"):
            updates["resolved_at"] = now
    if assigned_to is not None:
        updates["assigned_to"] = assigned_to
    if priority:
        updates["priority"] = priority

    if use_mongodb():
        from .mongo import Repository

        repo = Repository("complaints")
        row = repo.find_one({"ticket_id": ticket_id})
        if not row:
            return None
        repo.update({"ticket_id": ticket_id}, updates)
        return int(row["id"])

    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id, status FROM complaints WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not row:
            return None
        set_parts = []
        params = []
        for key, val in updates.items():
            set_parts.append(f"{key} = ?")
            params.append(val)
        params.append(ticket_id)
        conn.execute(
            f"UPDATE complaints SET {', '.join(set_parts)} WHERE ticket_id = ?",
            params,
        )
        return int(row["id"])


def resolve_complaint(ticket_id: str) -> Optional[int]:
    now = datetime.utcnow().isoformat()
    return update_complaint(
        ticket_id,
        status="resolved",
    )


def complaint_reply_row(ticket_id: str) -> Optional[dict]:
    return get_complaint(ticket_id)


def delete_complaint(ticket_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("complaints")
        row = repo.find_one({"ticket_id": ticket_id})
        if not row:
            return None
        repo.delete_one({"ticket_id": ticket_id})
        return dict(row)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id, wa_id, complaint_type, description FROM complaints WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM complaints WHERE ticket_id = ?", (ticket_id,))
        return dict(row)