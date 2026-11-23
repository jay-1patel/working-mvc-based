"""
Handoff timeout monitor.

Periodically checks for conversations stuck in human_handover mode
where no human agent has responded within the configured timeout.
When detected, automatically clears human_handover so the chatbot
resumes handling the conversation.

WhatsApp notify is OFF by default (HANDOFF_TIMEOUT_NOTIFY). Set to 1/true
to text the customer on auto-revert; state is always cleared either way.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from db.core import get_db_context, use_mongodb

logger = logging.getLogger("handoff_timeout")

# How often to check (seconds)
CHECK_INTERVAL = 60

# Max time a handoff can stay active before auto-revert (seconds)
HANDOFF_TIMEOUT_SECONDS = 3600  # 1 hour

TIMEOUT_MESSAGE = (
    "It looks like our team hasn't responded yet. "
    "I'm back to help you! Feel free to ask your question again. 🤖"
)


def _notify_enabled() -> bool:
    return os.environ.get("HANDOFF_TIMEOUT_NOTIFY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _parse_updated_at(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_stale_handoffs() -> list[str]:
    """Return wa_ids where human_handover=1 and no human reply has arrived
    within the timeout window.

    The cutoff is evaluated by SQLite itself (``datetime('now', ...)``) so it
    always uses the same clock that writes ``updated_at`` via CURRENT_TIMESTAMP.
    ``updated_at`` is bumped every time a human agent replies (see the
    agent-send route), so this fires only when the human agent has gone
    silent for the full timeout.
    """
    try:
        if use_mongodb():
            from db.mongo import Repository
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=HANDOFF_TIMEOUT_SECONDS)
            rows = Repository("user_states").find_all({"human_handover": 1}, limit=None)
            stale: list[str] = []
            for row in rows:
                updated = _parse_updated_at(row.get("updated_at"))
                if updated is not None and updated < cutoff:
                    wa_id = row.get("wa_id")
                    if wa_id:
                        stale.append(str(wa_id))
            return stale

        with get_db_context() as conn:
            rows = conn.execute(
                "SELECT wa_id, tenant_id FROM user_states "
                "WHERE human_handover = 1 "
                "AND updated_at < datetime('now', ?)",
                (f"-{HANDOFF_TIMEOUT_SECONDS} seconds",),
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Failed to check stale handoffs: {e}")
        return []


def _clear_handover(wa_id: str) -> None:
    """Clear human_handover for a single user."""
    try:
        from db.state import set_human_handover
        if set_human_handover(wa_id, False):
            logger.info(f"HANDOFF_TIMEOUT | Cleared handover for {wa_id}")
    except Exception as e:
        logger.error(f"Failed to clear handover for {wa_id}: {e}")


def _send_timeout_message(wa_id: str) -> None:
    """Send the auto-revert notification to the user (only when notify is on)."""
    try:
        from routing.config import SEND2_USERNAME, SEND2_PASSWORD
        if SEND2_USERNAME and SEND2_PASSWORD:
            from routing.whatsapp import send_whatsapp_message
            send_whatsapp_message(wa_id, TIMEOUT_MESSAGE)
            try:
                from services.send_log import log_whatsapp_send
                log_whatsapp_send(
                    wa_id=wa_id,
                    reason="handoff_timeout",
                    snippet=TIMEOUT_MESSAGE[:120],
                )
            except Exception:
                logger.exception("SEND_LOG_RECORD_FAILED | wa=%s reason=handoff_timeout", wa_id)
    except Exception as e:
        logger.error(f"Failed to send timeout message to {wa_id}: {e}")


async def handoff_timeout_monitor(stop_event: asyncio.Event = None) -> None:
    """Background loop that reverts stale handoffs."""
    notify = _notify_enabled()
    logger.info(
        "Handoff timeout monitor started (interval=%ds, timeout=%ds, notify=%s)",
        CHECK_INTERVAL, HANDOFF_TIMEOUT_SECONDS, int(notify),
    )

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("Handoff timeout monitor stopping")
            break

        try:
            stale = _get_stale_handoffs()
            if stale:
                notify = _notify_enabled()
                logger.info(
                    "HANDOFF_TIMEOUT | Found %s stale handoff(s) notify=%s: %s",
                    len(stale), int(notify), stale,
                )
                for wa_id in stale:
                    _clear_handover(wa_id)
                    if notify:
                        logger.info("HANDOFF_TIMEOUT | notify=1 | wa_id=%s", wa_id)
                        _send_timeout_message(wa_id)
                        await asyncio.sleep(1)
                    else:
                        logger.info("HANDOFF_TIMEOUT | notify=0 | wa_id=%s", wa_id)
        except Exception as e:
            logger.error(f"Handoff timeout check failed: {e}")

        await asyncio.sleep(CHECK_INTERVAL)