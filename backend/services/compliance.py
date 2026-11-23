"""
DPDP compliance: consent logging.
"""
import logging
from datetime import datetime, timezone

from database import get_db_context

logger = logging.getLogger("compliance")


def _use_mongodb():
    from db.core import use_mongodb
    return use_mongodb()


def log_consent(wa_id: str, consent_type: str, consent_text: str = None) -> None:
    """Idempotent consent log."""
    try:
        if _use_mongodb():
            from db.mongo import Repository

            repo = Repository("user_consents")
            existing = repo.find_one({"wa_id": wa_id, "consent_type": consent_type})
            if existing:
                if existing.get("opted_in"):
                    return
                repo.update(
                    {"id": existing["id"]},
                    {
                        "opted_in": 1,
                        "opted_in_at": datetime.now(timezone.utc),
                        "opted_out_at": None,
                    },
                )
            else:
                repo.insert({
                    "wa_id": wa_id,
                    "consent_type": consent_type,
                    "opted_in": 1,
                    "channel": "whatsapp",
                    "consent_text": consent_text or f"Implicit via {consent_type} on WhatsApp",
                    "opted_in_at": datetime.now(timezone.utc),
                })
            return
        with get_db_context() as conn:
            existing = conn.execute(
                "SELECT id, opted_in FROM user_consents "
                "WHERE wa_id = ? AND consent_type = ?",
                (wa_id, consent_type),
            ).fetchone()
            if existing:
                if existing[1]:
                    return  # already opted in
                conn.execute(
                    "UPDATE user_consents SET opted_in = 1, opted_in_at = CURRENT_TIMESTAMP, "
                    "opted_out_at = NULL WHERE id = ?",
                    (existing[0],),
                )
            else:
                conn.execute(
                    "INSERT INTO user_consents "
                    "(wa_id, consent_type, opted_in, channel, consent_text) "
                    "VALUES (?, ?, 1, 'whatsapp', ?)",
                    (wa_id, consent_type,
                     consent_text or f"Implicit via {consent_type} on WhatsApp"),
                )
    except Exception as e:
        logger.error(f"log_consent failed {wa_id}: {e}")