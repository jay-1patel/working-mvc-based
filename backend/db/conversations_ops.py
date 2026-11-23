"""Tenant-scoped conversations API backing store — dual SQLite / Mongo."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from .core import get_db, get_db_context, use_mongodb
from .inbox_ops import list_inbox_agents


def _normalize_lookup_phone(value: str) -> str:
    return re.sub(r"\D", "", str(value or "").strip())


def _state_wa_ids_mongo(tenant_id: str) -> set[str]:
    from .mongo import Repository

    return {
        str(r.get("wa_id") or "")
        for r in Repository("user_states").find_all({"tenant_id": tenant_id})
        if r.get("wa_id")
    }


def _chat_belongs_tenant(row: dict, tenant_id: str, legacy_wa: Optional[set[str]] = None) -> bool:
    tid = str(row.get("tenant_id") or "")
    if tid == str(tenant_id):
        return True
    if tid in ("", "None") and legacy_wa and str(row.get("wa_id") or "") in legacy_wa:
        return True
    return False


def list_tenant_conversations(
    *,
    tenant_id: str,
    limit: int = 100,
    search: Optional[str] = None,
) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        legacy_wa = _state_wa_ids_mongo(tenant_id)
        rows = [
            r for r in Repository("chat_history").find_all({})
            if _chat_belongs_tenant(r, tenant_id, legacy_wa)
        ]
        if search:
            needle = search.lower()
            rows = [
                r for r in rows
                if needle in str(r.get("wa_id") or "").lower()
                or needle in str(r.get("sender_name") or "").lower()
                or needle in str(r.get("message") or "").lower()
            ]
        grouped: dict[str, list] = {}
        for row in rows:
            wa = str(row.get("wa_id") or "")
            if wa:
                grouped.setdefault(wa, []).append(row)
        threads = []
        for wa_id, items in grouped.items():
            items.sort(key=lambda r: str(r.get("created_at") or ""))
            last = items[-1]
            inbound = sum(1 for r in items if not (r.get("response") or "").strip())
            state = Repository("user_states").find_one({"wa_id": wa_id, "tenant_id": tenant_id}) or Repository("user_states").find_one({"wa_id": wa_id})
            threads.append({
                "wa_id": wa_id,
                "last_message_at": last.get("created_at"),
                "turns": len(items),
                "inbound": inbound,
                "sender_name": last.get("sender_name"),
                "last_message": last.get("message"),
                "handover_mode": "human" if state and state.get("human_handover") else "bot",
                "bot_state": state.get("state") if state else None,
            })
        threads.sort(key=lambda t: str(t.get("last_message_at") or ""), reverse=True)
        return threads[:limit]

    tenant_scope = (
        "(ch.tenant_id = ? OR (ch.tenant_id IS NULL AND ch.wa_id IN "
        "(SELECT wa_id FROM user_states WHERE tenant_id = ?)))"
    )
    conn = get_db()
    try:
        sql = f"""
            SELECT
                ch.wa_id,
                MAX(ch.created_at) AS last_message_at,
                COUNT(*) AS turns,
                SUM(CASE WHEN ch.response IS NULL OR ch.response = '' THEN 1 ELSE 0 END) AS inbound
            FROM chat_history ch
            WHERE {tenant_scope}
        """
        params: list = [tenant_id, tenant_id]
        if search:
            sql += " AND (ch.wa_id LIKE ? OR ch.sender_name LIKE ? OR ch.message LIKE ?)"
            params.extend([f"%{search}%"] * 3)
        sql += " GROUP BY ch.wa_id ORDER BY last_message_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        threads = []
        for row in rows:
            wa_id = row["wa_id"]
            last = conn.execute(
                "SELECT message, sender_name FROM chat_history WHERE wa_id=? ORDER BY id DESC LIMIT 1",
                (wa_id,),
            ).fetchone()
            state = conn.execute(
                "SELECT human_handover FROM user_states WHERE tenant_id=? AND wa_id=?",
                (tenant_id, wa_id),
            ).fetchone()
            threads.append({
                "wa_id": wa_id,
                "last_message_at": row["last_message_at"],
                "turns": row["turns"],
                "inbound": row["inbound"],
                "sender_name": last["sender_name"] if last else None,
                "last_message": last["message"] if last else None,
                "handover_mode": "human" if state and state["human_handover"] else "bot",
                "bot_state": state["state"] if state else None,
            })
        return threads
    finally:
        conn.close()


def conversation_detail(tenant_id: str, wa_id: str, limit: int = 300) -> dict:
    if use_mongodb():
        from .mongo import Repository

        legacy_wa = _state_wa_ids_mongo(tenant_id)
        # find() defaults to limit=100 which silently truncates long threads and
        # can drop the latest messages the Chats panel needs. Use find_all.
        rows = [
            r for r in Repository("chat_history").find_all(
                {"wa_id": wa_id}, sort=[("created_at", 1), ("id", 1)]
            )
            if _chat_belongs_tenant(r, tenant_id, legacy_wa)
        ][-max(1, int(limit or 300)):]
        owns = bool(rows)
        if not owns:
            return {"owned": False, "messages": []}
        return {"owned": True, "messages": [dict(r) for r in rows]}

    tenant_scope = (
        "(ch.tenant_id = ? OR (ch.tenant_id IS NULL AND ch.wa_id IN "
        "(SELECT wa_id FROM user_states WHERE tenant_id = ?)))"
    )
    conn = get_db()
    try:
        owns = conn.execute(
            f"SELECT 1 FROM chat_history ch WHERE {tenant_scope} AND ch.wa_id = ? LIMIT 1",
            (tenant_id, tenant_id, wa_id),
        ).fetchone()
        if not owns:
            return {"owned": False, "messages": []}
        rows = conn.execute(
            f"""SELECT ch.* FROM chat_history ch
                WHERE {tenant_scope} AND ch.wa_id = ?
                ORDER BY ch.created_at ASC, ch.id ASC LIMIT ?""",
            (tenant_id, tenant_id, wa_id, limit),
        ).fetchall()
        return {"owned": True, "messages": [dict(r) for r in rows]}
    finally:
        conn.close()


def tenant_chat_history(
    *,
    tenant_id: str,
    days: int,
    search: Optional[str],
    wa_id: Optional[str],
    limit: int,
) -> dict:
    if use_mongodb():
        from .mongo import Repository

        legacy_wa = _state_wa_ids_mongo(tenant_id)
        rows = Repository("chat_history").find_all({}, sort=[("created_at", -1), ("id", -1)])
        cutoff = (datetime.utcnow().replace(microsecond=0)).isoformat()
        # naive days filter via string compare on SQLite-style timestamps
        from datetime import timedelta

        min_ts = (datetime.utcnow() - timedelta(days=days)).isoformat()
        out = []
        for row in rows:
            if not _chat_belongs_tenant(row, tenant_id, legacy_wa):
                continue
            if str(row.get("created_at") or "") < min_ts:
                continue
            if wa_id and str(row.get("wa_id") or "") != wa_id:
                continue
            if search:
                needle = search.lower()
                if not any(
                    needle in str(row.get(field) or "").lower()
                    for field in ("wa_id", "sender_name", "message", "response")
                ):
                    continue
            out.append(dict(row))
            if len(out) >= limit:
                break
        return {"history": out}

    tenant_scope = (
        "(ch.tenant_id = ? OR (ch.tenant_id IS NULL AND ch.wa_id IN "
        "(SELECT wa_id FROM user_states WHERE tenant_id = ?)))"
    )
    conn = get_db()
    try:
        sql = f"""SELECT ch.* FROM chat_history ch
                  WHERE {tenant_scope}
                    AND ch.created_at >= DATE('now', ?)"""
        params: list = [tenant_id, tenant_id, f"-{days} days"]
        if wa_id:
            sql += " AND ch.wa_id = ?"
            params.append(wa_id)
        if search:
            sql += " AND (ch.wa_id LIKE ? OR ch.sender_name LIKE ? OR ch.message LIKE ? OR ch.response LIKE ?)"
            params.extend([f"%{search}%"] * 4)
        sql += " ORDER BY ch.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return {"history": [dict(r) for r in rows]}
    finally:
        conn.close()


def tenant_inbox_queue(tenant_id: str, include_resolved: bool = False) -> dict:
    if use_mongodb():
        from .mongo import Repository

        legacy_wa = _state_wa_ids_mongo(tenant_id)
        chats = [
            r for r in Repository("chat_history").find_all({})
            if _chat_belongs_tenant(r, tenant_id, legacy_wa)
        ]
        states = {
            str(r.get("wa_id")): r
            for r in Repository("user_states").find_all({"tenant_id": tenant_id})
        }
        assignments = {
            str(r.get("wa_id")): r.get("agent_id")
            for r in Repository("conversation_assignments").find_all({"tenant_id": tenant_id})
        }
        grouped: dict[str, list] = {}
        for row in chats:
            wa = str(row.get("wa_id") or "")
            if wa:
                grouped.setdefault(wa, []).append(row)
        conversations = []
        for wa_id, rows in grouped.items():
            state = states.get(wa_id) or Repository("user_states").find_one({"wa_id": wa_id}) or {}
            if not include_resolved and state.get("handover_resolved_at"):
                continue
            last = sorted(rows, key=lambda r: str(r.get("created_at") or ""))[-1]
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
                "resolved": bool(state.get("handover_resolved_at")),
            })
        conversations.sort(key=lambda c: str(c.get("last_message_at") or ""), reverse=True)
        return {"conversations": conversations}

    tenant_scope = (
        "(ch.tenant_id = ? OR (ch.tenant_id IS NULL AND ch.wa_id IN "
        "(SELECT wa_id FROM user_states WHERE tenant_id = ?)))"
    )
    conn = get_db()
    try:
        resolved_clause = "" if include_resolved else " AND us.handover_resolved_at IS NULL"
        rows = conn.execute(
            f"""
            SELECT
                ch.wa_id,
                MAX(ch.created_at) AS last_message_at,
                (SELECT message FROM chat_history ch2 WHERE ch2.wa_id = ch.wa_id ORDER BY ch2.id DESC LIMIT 1) AS last_message,
                (SELECT COUNT(*) FROM chat_history ch3 WHERE ch3.wa_id = ch.wa_id) AS unread_count,
                COALESCE(us.human_handover, 0) AS human_handover,
                CASE WHEN us.handover_resolved_at IS NOT NULL THEN 1 ELSE 0 END AS resolved
            FROM chat_history ch
            LEFT JOIN user_states us ON us.wa_id = ch.wa_id AND us.tenant_id = ?
            WHERE {tenant_scope.replace('ch.', 'ch.')}
            {resolved_clause}
            GROUP BY ch.wa_id
            ORDER BY last_message_at DESC
            """,
            (tenant_id, tenant_id, tenant_id),
        ).fetchall()
        conversations = []
        for row in rows:
            wa_id = row["wa_id"]
            assignment = conn.execute(
                "SELECT agent_id FROM conversation_assignments WHERE tenant_id = ? AND wa_id = ?",
                (tenant_id, wa_id),
            ).fetchone()
            assigned = assignment["agent_id"] if assignment else None
            conversations.append({
                "wa_id": wa_id,
                "name": wa_id,
                "last_message": row["last_message"] or "",
                "last_message_at": row["last_message_at"],
                "unread_count": row["unread_count"] or 0,
                "priority": "normal",
                "assigned_agent_id": assigned,
                "assigned_agent_name": assigned,
                "resolved": bool(row["resolved"]),
                "handover_mode": "human" if row["human_handover"] else "bot",
            })
        return {"conversations": conversations}
    finally:
        conn.close()


def tenant_owns_conversation(tenant_id: str, wa_id: str) -> bool:
    detail = conversation_detail(tenant_id, wa_id, limit=1)
    return bool(detail.get("owned"))


def list_tenant_agents() -> dict:
    return {"agents": list_inbox_agents()}


def list_tenant_complaints(tenant_id: str, status: Optional[str], limit: int) -> dict:
    if use_mongodb():
        from .mongo import Repository

        flt: dict[str, Any] = {"tenant_id": tenant_id}
        if status:
            flt["status"] = status
        rows = Repository("complaints").find(flt, sort=[("created_at", -1), ("id", -1)], limit=limit)
        complaints = []
        for r in rows:
            item = dict(r)
            item["name"] = item.get("wa_id") or "unknown"
            chats = Repository("chat_history").find(
                {"wa_id": item.get("wa_id"), "$or": [{"response": None}, {"response": ""}]},
                sort=[("id", -1)],
                limit=1,
            )
            item["last_user_message"] = (chats[0].get("message") if chats else "") or ""
            complaints.append(item)
        open_count = Repository("complaints").count({"tenant_id": tenant_id, "status": "open"})
        return {"complaints": complaints, "count": len(complaints), "open_count": open_count}

    conn = get_db()
    try:
        sql = "SELECT * FROM complaints WHERE tenant_id = ?"
        params: list = [tenant_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        complaints = []
        for r in rows:
            item = dict(r)
            item["name"] = item.get("wa_id") or "unknown"
            user_row = conn.execute(
                "SELECT message FROM chat_history WHERE wa_id = ? "
                "AND (response IS NULL OR response = '') ORDER BY id DESC LIMIT 1",
                (item.get("wa_id"),),
            ).fetchone()
            item["last_user_message"] = (user_row["message"] if user_row else "") or ""
            complaints.append(item)
        open_count = conn.execute(
            "SELECT COUNT(*) AS c FROM complaints WHERE tenant_id = ? AND status = 'open'",
            (tenant_id,),
        ).fetchone()["c"]
        return {"complaints": complaints, "count": len(complaints), "open_count": open_count or 0}
    finally:
        conn.close()


def update_tenant_complaint(
    tenant_id: str,
    ticket_id: str,
    *,
    status: Optional[str],
    priority: Optional[str],
    assigned_to: Optional[str],
) -> None:
    now = datetime.utcnow().isoformat()
    updates: dict[str, Any] = {"updated_at": now}
    if status:
        updates["status"] = status
        if status in ("resolved", "closed"):
            updates["resolved_at"] = now
    if priority:
        updates["priority"] = priority
    if assigned_to is not None:
        updates["assigned_to"] = assigned_to

    if use_mongodb():
        from .mongo import Repository

        row = Repository("complaints").find_one({"ticket_id": ticket_id, "tenant_id": tenant_id})
        if not row:
            raise LookupError("Complaint not found for this tenant")
        Repository("complaints").update({"id": row["id"]}, updates)
        return

    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id FROM complaints WHERE ticket_id = ? AND tenant_id = ?",
            (ticket_id, tenant_id),
        ).fetchone()
        if not row:
            raise LookupError("Complaint not found for this tenant")
        fields, params = [], []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            params.append(value)
        params.extend([ticket_id, tenant_id])
        conn.execute(
            f"UPDATE complaints SET {', '.join(fields)} WHERE ticket_id = ? AND tenant_id = ?",
            params,
        )


def complaint_wa_id(tenant_id: str, ticket_id: str) -> Optional[str]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("complaints").find_one({"ticket_id": ticket_id, "tenant_id": tenant_id})
        return row.get("wa_id") if row else None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT wa_id FROM complaints WHERE ticket_id = ? AND tenant_id = ?",
            (ticket_id, tenant_id),
        ).fetchone()
        return row["wa_id"] if row else None
    finally:
        conn.close()


def patch_complaint_status(tenant_id: str, ticket_id: str, status: str) -> None:
    update_tenant_complaint(tenant_id, ticket_id, status=status, priority=None, assigned_to=None)


def delete_tenant_complaint(tenant_id: str, ticket_id: str) -> None:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("complaints").find_one({"ticket_id": ticket_id, "tenant_id": tenant_id})
        if not row:
            raise LookupError("Complaint not found for this tenant")
        Repository("complaints").delete_one({"id": row["id"]})
        return
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id FROM complaints WHERE ticket_id = ? AND tenant_id = ?",
            (ticket_id, tenant_id),
        ).fetchone()
        if not row:
            raise LookupError("Complaint not found for this tenant")
        conn.execute(
            "DELETE FROM complaints WHERE ticket_id = ? AND tenant_id = ?",
            (ticket_id, tenant_id),
        )


def customer_360_view(tenant_id: str, digits: str, limit: int) -> dict:
    if use_mongodb():
        from .mongo import Repository

        customer = Repository("customers").find_one({"tenant_id": tenant_id, "wa_id": digits})
        if customer is None:
            for row in Repository("customers").find_all({"tenant_id": tenant_id}):
                phone = _normalize_lookup_phone(row.get("phone"))
                if phone == digits:
                    customer = row
                    break
        resolved_wa = str(customer.get("wa_id") or digits) if customer else digits

        def fetch(table, flt, lim=limit):
            try:
                return [dict(r) for r in Repository(table).find(flt, sort=[("created_at", -1), ("id", -1)], limit=lim)]
            except Exception:
                return []

        session = Repository("user_sessions").find_one({"tenant_id": tenant_id, "wa_id": resolved_wa})
        if session is None:
            session = Repository("user_sessions").find_one({"wa_id": resolved_wa})
        state = Repository("user_states").find_one({"tenant_id": tenant_id, "wa_id": resolved_wa})
        if state is None:
            state = Repository("user_states").find_one({"wa_id": resolved_wa})
        chat = list(reversed(fetch("chat_history", {"tenant_id": tenant_id, "wa_id": resolved_wa})))
        orders = fetch("orders", {"tenant_id": tenant_id, "wa_id": resolved_wa})
        leads = fetch("leads", {"tenant_id": tenant_id, "wa_id": resolved_wa})
        complaints = fetch("complaints", {"tenant_id": tenant_id, "wa_id": resolved_wa})
        handoffs = fetch("handoffs", {"tenant_id": tenant_id, "wa_id": resolved_wa})
        send_log = fetch(
            "whatsapp_send_log",
            {"wa_id": resolved_wa, "tenant_id": tenant_id},
            lim=min(limit, 50),
        )
        dedup = fetch("webhook_dedup", {"wa_id": resolved_wa}, lim=min(limit, 50))
        webhook_hits = fetch(
            "webhook_logs",
            {"wa_id": resolved_wa, "tenant_id": tenant_id},
            lim=min(limit, 50),
        )
        return {
            "tenant_id": tenant_id,
            "wa_id": resolved_wa,
            "lookup": digits,
            "customer": dict(customer) if customer else None,
            "session": dict(session) if session else None,
            "state": dict(state) if state else None,
            "chat_history": chat,
            "orders": orders,
            "leads": leads,
            "complaints": complaints,
            "handoffs": handoffs,
            "whatsapp_send_log": send_log,
            "processed_inbound": dedup,
            "webhook_logs": webhook_hits,
        }

    with get_db_context() as conn:
        customer = conn.execute(
            """SELECT * FROM customers
               WHERE tenant_id = ?
                 AND (wa_id = ? OR phone = ? OR replace(replace(coalesce(phone,''),'+',''),' ','') = ?)
               LIMIT 1""",
            (tenant_id, digits, digits, digits),
        ).fetchone()
        resolved_wa = digits
        if customer:
            resolved_wa = str(customer["wa_id"] or digits)
        session = conn.execute(
            "SELECT * FROM user_sessions WHERE tenant_id = ? AND wa_id = ?",
            (tenant_id, resolved_wa),
        ).fetchone()
        if session is None:
            session = conn.execute(
                "SELECT * FROM user_sessions WHERE wa_id = ? LIMIT 1",
                (resolved_wa,),
            ).fetchone()
        state = conn.execute(
            "SELECT * FROM user_states WHERE tenant_id = ? AND wa_id = ?",
            (tenant_id, resolved_wa),
        ).fetchone()
        if state is None:
            state = conn.execute(
                "SELECT * FROM user_states WHERE wa_id = ? LIMIT 1",
                (resolved_wa,),
            ).fetchone()
        chat = conn.execute(
            """SELECT id, message, response, route, created_at FROM chat_history
               WHERE tenant_id = ? AND wa_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (tenant_id, resolved_wa, limit),
        ).fetchall()
        try:
            orders = conn.execute(
                """SELECT * FROM orders
                   WHERE (tenant_id = ? OR tenant_id IS NULL) AND wa_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (tenant_id, resolved_wa, limit),
            ).fetchall()
        except Exception:
            orders = []
        try:
            leads = conn.execute(
                """SELECT * FROM leads WHERE tenant_id = ? AND wa_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (tenant_id, resolved_wa, limit),
            ).fetchall()
        except Exception:
            leads = []
        try:
            complaints = conn.execute(
                """SELECT * FROM complaints
                   WHERE (tenant_id = ? OR tenant_id IS NULL) AND wa_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (tenant_id, resolved_wa, limit),
            ).fetchall()
        except Exception:
            complaints = []
        try:
            handoffs = conn.execute(
                """SELECT * FROM handoffs WHERE tenant_id = ? AND wa_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (tenant_id, resolved_wa, limit),
            ).fetchall()
        except Exception:
            handoffs = []
        try:
            send_log = conn.execute(
                """SELECT id, reason, trigger_message_id, snippet, created_at
                   FROM whatsapp_send_log
                   WHERE wa_id = ? AND (tenant_id = ? OR tenant_id IS NULL OR tenant_id = '')
                   ORDER BY created_at DESC LIMIT ?""",
                (resolved_wa, tenant_id, limit),
            ).fetchall()
        except Exception:
            send_log = []
        try:
            dedup = conn.execute(
                """SELECT message_id, channel, processed_at FROM processed_inbound_messages
                   WHERE wa_id = ? ORDER BY processed_at DESC LIMIT ?""",
                (resolved_wa, min(limit, 50)),
            ).fetchall()
        except Exception:
            dedup = []
        try:
            webhook_hits = conn.execute(
                """SELECT id, direction, endpoint, status_code, message_id, created_at
                   FROM webhook_logs
                   WHERE wa_id = ? AND (tenant_id = ? OR tenant_id IS NULL OR tenant_id = '')
                   ORDER BY created_at DESC LIMIT ?""",
                (resolved_wa, tenant_id, min(limit, 50)),
            ).fetchall()
        except Exception:
            webhook_hits = []
        return {
            "tenant_id": tenant_id,
            "wa_id": resolved_wa,
            "lookup": digits,
            "customer": dict(customer) if customer else None,
            "session": dict(session) if session else None,
            "state": dict(state) if state else None,
            "chat_history": list(reversed([dict(r) for r in chat])),
            "orders": [dict(r) for r in orders],
            "leads": [dict(r) for r in leads],
            "complaints": [dict(r) for r in complaints],
            "handoffs": [dict(r) for r in handoffs],
            "whatsapp_send_log": [dict(r) for r in send_log],
            "processed_inbound": [dict(r) for r in dedup],
            "webhook_logs": [dict(r) for r in webhook_hits],
        }
