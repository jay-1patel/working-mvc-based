"""
WhatsApp outbox for reliable sends with retry + admin notification gating.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from database import get_db_context

logger = logging.getLogger("outbox")
MAX_ATTEMPTS = 3
BACKOFF_BASE = 2


def _use_mongodb():
    from db.core import use_mongodb
    if not use_mongodb():
        return False
    try:
        from db.mongo import schema
        schema("whatsapp_outbox")
        return True
    except ValueError:
        return False


def _outbox_repo():
    from db.mongo import Repository
    return Repository("whatsapp_outbox")


def _parse_next_retry(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    if "T" in text:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def enqueue_message(wa_id: str, message_type: str, payload: dict) -> int:
    try:
        now = datetime.now(timezone.utc)
        if _use_mongodb():
            row = _outbox_repo().insert({
                "wa_id": wa_id,
                "message_type": message_type,
                "payload": payload,
                "status": "pending",
                "attempts": 0,
                "next_retry": now,
            })
            return int(row.get("id") or -1)
        with get_db_context() as conn:
            cur = conn.execute(
                "INSERT INTO whatsapp_outbox "
                "(wa_id, message_type, payload, status, attempts, next_retry) "
                "VALUES (?, ?, ?, 'pending', 0, CURRENT_TIMESTAMP)",
                (wa_id, message_type, json.dumps(payload)),
            )
            return cur.lastrowid
    except Exception as e:
        logger.error(f"Failed to enqueue message for {wa_id}: {e}")
        return -1


async def send_text_safe(wa_id: str, text: str) -> bool:
    """Immediate send; on failure → outbox retry queue."""
    from backend.services.whatsapp_sender import send_text_message
    try:
        return await send_text_message(wa_id, text)
    except Exception as e:
        logger.error(f"send_text_safe failed for {wa_id}: {e}")
        enqueue_message(wa_id, "text", {"body": text})
        return False


async def send_button_safe(wa_id: str, body_text: str, buttons: list,
                         header_media: dict = None) -> bool:
    from backend.services.whatsapp_sender import send_button_message
    try:
        return await send_button_message(wa_id, body_text, buttons, header_media)
    except Exception as e:
        logger.error(f"send_button_safe failed for {wa_id}: {e}")
        enqueue_message(wa_id, "button", {
            "body": body_text, "buttons": buttons, "header_media": header_media,
        })
        return False


def notify_admin(message: str) -> None:
    """
    Admin pings gated: sending outside the 24h window fails in live mode.
    ADMIN_NOTIFICATION_MODE=log (default, safe) | send
    """
    mode = os.getenv("ADMIN_NOTIFICATION_MODE", "log")
    if mode == "log":
        logger.info(f"[ADMIN NOTIFICATION] {message}")
        return
    admin_wa_id = os.getenv("ADMIN_WHATSAPP_ID")
    if not admin_wa_id:
        logger.warning("ADMIN_WHATSAPP_ID not set")
        return
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        from backend.services.whatsapp_sender import send_text_message
        if loop.is_running():
            asyncio.ensure_future(send_text_message(admin_wa_id, message))
        else:
            loop.run_until_complete(send_text_message(admin_wa_id, message))
    except Exception as e:
        logger.warning(f"Admin notification failed: {e}")
        logger.info(f"[ADMIN NOTIFICATION FALLBACK] {message}")


def _mark_sent(row_id):
    now = datetime.now(timezone.utc)
    if _use_mongodb():
        _outbox_repo().update({"id": row_id}, {"status": "sent", "sent_at": now})
        return
    with get_db_context() as conn:
        conn.execute(
            "UPDATE whatsapp_outbox SET status='sent', "
            "sent_at=CURRENT_TIMESTAMP WHERE id=?",
            (row_id,),
        )


def _mark_retry(row_id, attempts: int, new_status: str, next_retry):
    if _use_mongodb():
        _outbox_repo().update(
            {"id": row_id},
            {"attempts": attempts, "next_retry": next_retry, "status": new_status},
        )
        return
    with get_db_context() as conn:
        conn.execute(
            "UPDATE whatsapp_outbox SET attempts=?, "
            "next_retry=?, status=? WHERE id=?",
            (attempts, next_retry, new_status, row_id),
        )


def drain_outbox() -> None:
    """Run via cron/background thread every ~30s."""
    now = datetime.now(timezone.utc)
    try:
        if _use_mongodb():
            repo = _outbox_repo()
            candidates = repo.find_all({"status": "pending"}, sort=[("id", 1)], limit=None)
            rows = []
            for row in candidates:
                if int(row.get("attempts") or 0) >= MAX_ATTEMPTS:
                    continue
                if _parse_next_retry(row.get("next_retry")) <= now:
                    rows.append(row)
                if len(rows) >= 50:
                    break
        else:
            with get_db_context() as conn:
                rows = conn.execute(
                    "SELECT * FROM whatsapp_outbox WHERE status='pending' "
                    "AND attempts < ? AND next_retry <= CURRENT_TIMESTAMP "
                    "ORDER BY id ASC LIMIT 50",
                    (MAX_ATTEMPTS,),
                ).fetchall()
    except Exception as e:
        logger.error(f"Outbox drain query failed: {e}")
        return

    for row in rows:
        try:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            import asyncio
            loop = asyncio.get_event_loop()
            if row["message_type"] == "text":
                from backend.services.whatsapp_sender import send_text_message
                coro = send_text_message(row["wa_id"], payload["body"])
            elif row["message_type"] == "button":
                from backend.services.whatsapp_sender import send_button_message
                coro = send_button_message(
                    row["wa_id"], payload["body"], payload["buttons"],
                    payload.get("header_media"),
                )
            else:
                continue

            if loop.is_running():
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(coro)

            _mark_sent(row["id"])
        except Exception as e:
            attempts = int(row.get("attempts") or 0) + 1
            new_status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
            next_retry = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(
                seconds=BACKOFF_BASE ** attempts
            )
            _mark_retry(row["id"], attempts, new_status, next_retry)
            logger.error(
                f"Outbox send failed (attempt {attempts}) for {row['wa_id']}: {e}"
            )