"""Live inbox queue — dual SQLite / Mongo backend."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .core import get_db, get_db_context, use_mongodb


def get_inbox_queue() -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        chats = Repository("chat_history")
        states = {f"{r.get('wa_id')}": r for r in Repository("user_states").find_all({})}
        assignments = {
            str(r.get("wa_id")): r.get("agent_id")
            for r in Repository("conversation_assignments").find_all({})
        }
        by_wa: dict[str, list] = defaultdict(list)
        for row in chats.find_all({}, sort=[("created_at", 1), ("id", 1)]):
            wa = str(row.get("wa_id") or "")
            if wa:
                by_wa[wa].append(row)
        conversations = []
        for wa_id, rows in by_wa.items():
            state = states.get(wa_id) or {}
            if state.get("handover_resolved_at"):
                continue
            last = rows[-1]
            conversations.append({
                "wa_id": wa_id,
                "name": wa_id,
                "last_message": last.get("message") or "",
                "last_message_at": last.get("created_at"),
                "unread_count": len(rows),
                "priority": "normal",
                "assigned_agent_id": assignments.get(wa_id),
                "assigned_agent_name": assignments.get(wa_id),
                "handover_mode": "human" if state.get("human_handover") else "bot",
            })
        conversations.sort(
            key=lambda c: str(c.get("last_message_at") or ""),
            reverse=True,
        )
        return conversations

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                ch.wa_id,
                MAX(ch.created_at) AS last_message_at,
                (SELECT message FROM chat_history ch2
                 WHERE ch2.wa_id = ch.wa_id ORDER BY ch2.id DESC LIMIT 1) AS last_message,
                (SELECT COUNT(*) FROM chat_history ch3
                 WHERE ch3.wa_id = ch.wa_id) AS unread_count,
                us.state AS bot_state,
                COALESCE(us.human_handover, 0) AS human_handover,
                (SELECT context_json FROM user_states us2
                 WHERE us2.wa_id = ch.wa_id) AS context_json
            FROM chat_history ch
            LEFT JOIN user_states us ON us.wa_id = ch.wa_id
            WHERE us.handover_resolved_at IS NULL
            GROUP BY ch.wa_id
            ORDER BY last_message_at DESC
            """
        ).fetchall()
        conversations = []
        for row in rows:
            wa_id = row["wa_id"]
            handover = bool(row["human_handover"])
            assignment = conn.execute(
                "SELECT agent_id FROM conversation_assignments WHERE wa_id = ?",
                (wa_id,),
            ).fetchone()
            assigned_agent_id = assignment["agent_id"] if assignment else None
            conversations.append({
                "wa_id": wa_id,
                "name": wa_id,
                "last_message": row["last_message"] or "",
                "last_message_at": row["last_message_at"],
                "unread_count": row["unread_count"] or 0,
                "priority": "normal",
                "assigned_agent_id": assigned_agent_id,
                "assigned_agent_name": assigned_agent_id,
                "handover_mode": "human" if handover else "bot",
            })
        return conversations
    finally:
        conn.close()


def list_inbox_agents() -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        admins = Repository("admins").find_all(sort=[("username", 1)])
        status_by_id = {
            r.get("agent_id"): r.get("status") or "offline"
            for r in Repository("agent_status").find_all({})
        }
        active_chats = Repository("user_states").count({"human_handover": 1})
        return [
            {
                "agent_id": a.get("username"),
                "username": a.get("username"),
                "status": status_by_id.get(a.get("username"), "offline"),
                "active_chats": active_chats,
            }
            for a in admins
        ]

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                a.username AS agent_id,
                a.username,
                COALESCE(ao.status, 'offline') AS status,
                (SELECT COUNT(DISTINCT us.wa_id)
                 FROM user_states us
                 WHERE us.human_handover = 1
                ) AS active_chats
            FROM admins a
            LEFT JOIN agent_status ao ON ao.agent_id = a.username
            ORDER BY a.username
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_agent_status(agent_id: str, status: str) -> None:
    ts = datetime.utcnow().isoformat()
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("agent_status")
        existing = repo.find_one({"agent_id": agent_id})
        if existing:
            repo.update({"agent_id": agent_id}, {"status": status, "updated_at": ts})
        else:
            repo.insert({"agent_id": agent_id, "status": status, "updated_at": ts})
        return
    with get_db_context() as conn:
        conn.execute(
            """
            INSERT INTO agent_status (agent_id, status, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
            """,
            (agent_id, status, ts),
        )


def assign_conversation(tenant_id: str, wa_id: str, agent_id: str) -> None:
    ts = datetime.utcnow().isoformat()
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("conversation_assignments")
        existing = repo.find_one({"tenant_id": tenant_id, "wa_id": wa_id})
        if existing:
            repo.update(
                {"tenant_id": tenant_id, "wa_id": wa_id},
                {"agent_id": agent_id, "assigned_at": ts},
            )
        else:
            repo.insert({
                "tenant_id": tenant_id,
                "wa_id": wa_id,
                "agent_id": agent_id,
                "assigned_at": ts,
            })
        return
    with get_db_context() as conn:
        conn.execute(
            """
            INSERT INTO conversation_assignments (tenant_id, wa_id, agent_id, assigned_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
              agent_id=excluded.agent_id, assigned_at=excluded.assigned_at
            """,
            (tenant_id, wa_id, agent_id, ts),
        )


def reset_bot_state(wa_id: str) -> None:
    ts = datetime.utcnow().isoformat()
    if use_mongodb():
        from .mongo import Repository

        Repository("user_states").update(
            {"wa_id": wa_id},
            {"state": "MAIN_MENU", "context_json": "{}", "updated_at": ts},
        )
        return
    with get_db_context() as conn:
        conn.execute(
            """
            UPDATE user_states
            SET state = 'MAIN_MENU', context_json = '{}', updated_at = ?
            WHERE wa_id = ?
            """,
            (ts, wa_id),
        )


def delete_conversation_data(wa_id: str) -> None:
    if use_mongodb():
        from .mongo import Repository

        Repository("chat_history").delete_many({"wa_id": wa_id})
        Repository("user_states").delete_many({"wa_id": wa_id})
        Repository("conversation_assignments").delete_many({"wa_id": wa_id})
        return
    with get_db_context() as conn:
        conn.execute("DELETE FROM chat_history WHERE wa_id = ?", (wa_id,))
        conn.execute("DELETE FROM user_states WHERE wa_id = ?", (wa_id,))
        conn.execute("DELETE FROM conversation_assignments WHERE wa_id = ?", (wa_id,))