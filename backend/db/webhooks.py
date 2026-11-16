"""Webhook request/response logging and inbound dedupe data access — extracted from backend/database.py."""
import json
import hashlib
from datetime import datetime

from .core import logger, get_db_context, use_mongodb


WEBHOOK_LOG_MAX_ROWS = 5000


def log_webhook(
    direction,
    endpoint,
    payload,
    status_code=None,
    notes=None,
    response_time_ms=None,
    wa_id=None,
    tenant_id=None,
    message_id=None,
):
    # SECURITY FIX: Store payload hash instead of raw payload to prevent sensitive data leakage
    try:
        payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
        # Compute hash of the payload for secure storage
        payload_hash = hashlib.sha256(payload_str.encode('utf-8', errors='replace')).hexdigest()
        payload_size = len(payload_str)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if use_mongodb():
            from .mongo import Repository
            Repository("webhook_logs").insert({
                "direction": direction,
                "endpoint": endpoint,
                "payload_hash": payload_hash,
                "payload_size": payload_size,
                "status_code": status_code,
                "notes": notes,
                "response_time_ms": response_time_ms,
                "wa_id": wa_id,
                "tenant_id": tenant_id,
                "message_id": message_id,
                "created_at": created_at,
            })
            _trim_webhook_logs(None)
            return
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO webhook_logs "
                "(direction, endpoint, payload_hash, payload_size, status_code, notes, "
                "response_time_ms, wa_id, tenant_id, message_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    direction,
                    endpoint,
                    payload_hash,
                    payload_size,
                    status_code,
                    notes,
                    response_time_ms,
                    wa_id,
                    tenant_id,
                    message_id,
                    created_at,
                ),
            )
            _trim_webhook_logs(conn)
    except Exception as e:
        logger.error(f"Failed to log webhook: {e}")


def _trim_webhook_logs(conn, max_rows: int = WEBHOOK_LOG_MAX_ROWS):
    try:
        if use_mongodb() or conn is None:
            from .mongo import Repository
            repo = Repository("webhook_logs")
            count = repo.count()
            if count > max_rows:
                excess = count - max_rows
                oldest = repo.find_all(sort=[("created_at", 1), ("id", 1)], limit=excess)
                ids = [row["id"] for row in oldest if row.get("id") is not None]
                if ids:
                    repo.delete_many({"id": {"$in": ids}})
            return
        count = conn.execute("SELECT COUNT(*) FROM webhook_logs").fetchone()[0]
        if count > max_rows:
            excess = count - max_rows
            conn.execute(
                "DELETE FROM webhook_logs WHERE id IN "
                "(SELECT id FROM webhook_logs ORDER BY created_at ASC, id ASC LIMIT ?)",
                (excess,),
            )
    except Exception as e:
        logger.error(f"Failed to trim webhook_logs: {e}")


def get_webhook_stats():
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("webhook_logs")
        total = repo.count()
        incoming = repo.count({"direction": "incoming"})
        outgoing = repo.count({"direction": "outgoing"})
        last_in = repo.find({"direction": "incoming"}, sort=[("created_at", -1)], limit=1)
        last_out = repo.find({"direction": "outgoing"}, sort=[("created_at", -1)], limit=1)
        return {
            "total": total,
            "incoming": incoming,
            "outgoing": outgoing,
            "last_incoming": last_in[0]["created_at"] if last_in else None,
            "last_outgoing": last_out[0]["created_at"] if last_out else None,
        }
    with get_db_context() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM webhook_logs").fetchone()["cnt"]
        incoming = conn.execute("SELECT COUNT(*) as cnt FROM webhook_logs WHERE direction = 'incoming'").fetchone()["cnt"]
        outgoing = conn.execute("SELECT COUNT(*) as cnt FROM webhook_logs WHERE direction = 'outgoing'").fetchone()["cnt"]
        last_in = conn.execute("SELECT created_at FROM webhook_logs WHERE direction = 'incoming' ORDER BY created_at DESC LIMIT 1").fetchone()
        last_out = conn.execute("SELECT created_at FROM webhook_logs WHERE direction = 'outgoing' ORDER BY created_at DESC LIMIT 1").fetchone()
        return {
            "total": total,
            "incoming": incoming,
            "outgoing": outgoing,
            "last_incoming": last_in["created_at"] if last_in else None,
            "last_outgoing": last_out["created_at"] if last_out else None,
        }


def was_inbound_processed(message_id: str, channel: str = "send2") -> bool:
    """True if this channel or the webhook already processed the message (survives restarts).

    Used by the send2 poller and webhook receiver so a restart or dual-path
    delivery does not double-answer the message.
    """
    if not message_id:
        return False
    try:
        if use_mongodb():
            from .mongo import Repository
            if Repository("processed_inbound_messages").find_one({"message_id": message_id}):
                return True
            return Repository("webhook_dedup").find_one({"message_id": message_id}) is not None
        with get_db_context() as conn:
            row1 = conn.execute(
                "SELECT 1 FROM processed_inbound_messages WHERE message_id=?",
                (message_id,),
            ).fetchone()
            if row1 is not None:
                return True
            row2 = conn.execute(
                "SELECT 1 FROM webhook_dedup WHERE message_id=?",
                (message_id,),
            ).fetchone()
            return row2 is not None
    except Exception as e:
        # Fail closed: treat as already processed so a locked DB cannot
        # re-answer the poller's 15-minute window.
        logger.error(
            "DEDUP_FAIL_CLOSED | was_inbound_processed check failed for %s: %s",
            message_id, e,
        )
        return True


def mark_inbound_processed(message_id: str, wa_id: str, channel: str = "send2") -> None:
    if not message_id:
        return
    try:
        if use_mongodb():
            from .mongo import Repository
            processed = Repository("processed_inbound_messages")
            if not processed.find_one({"message_id": message_id}):
                processed.insert({
                    "message_id": message_id,
                    "wa_id": wa_id,
                    "channel": channel,
                })
            dedup = Repository("webhook_dedup")
            if not dedup.find_one({"message_id": message_id}):
                dedup.insert({
                    "message_id": message_id,
                    "wa_id": wa_id,
                    "processed_at": datetime.utcnow(),
                })
            return
        with get_db_context() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_inbound_messages (message_id, wa_id, channel) VALUES (?, ?, ?)",
                (message_id, wa_id, channel),
            )
            conn.execute(
                "INSERT OR IGNORE INTO webhook_dedup (message_id, wa_id, processed_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (message_id, wa_id),
            )
    except Exception as e:
        logger.error(f"mark_inbound_processed failed for {message_id}: {e}")
