"""
Cron jobs for B2C cart/checkout maintenance.

Run periodically via a background thread or external cron.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("cron")

# Sliding 7-day cart TTL (in days)
CART_TTL_DAYS = 7
CHECKOUT_TTL_DAYS = 1


def _dedup_repo():
    from db.mongo import Repository
    return Repository("webhook_dedup")


def _outbox_repo():
    from db.mongo import Repository
    return Repository("whatsapp_outbox")


def _carts_repo():
    from db.mongo import Repository
    return Repository("carts")


def _checkout_repo():
    from db.mongo import Repository
    return Repository("checkout_sessions")


def cleanup_dedup_table():
    """Remove dedup records older than 24 hours."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        deleted = _dedup_repo().delete_many({"processed_at": {"$lt": cutoff}})
        if deleted:
            logger.info(f"Cleaned {deleted} dedup records")
    except Exception as e:
        logger.error(f"Dedup cleanup failed: {e}")


def cleanup_outbox():
    """Mark old failed outbox entries as dead-letter."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        repo = _outbox_repo()
        count = 0
        for row in repo.find_all({"status": "failed"}, limit=None):
            if int(row.get("attempts") or 0) < 3:
                continue
            created = row.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created and created < cutoff:
                if repo.update({"id": row["id"]}, {"status": "dead_letter"}):
                    count += 1
        if count:
            logger.info(f"Dead-lettered {count} outbox entries")
    except Exception as e:
        logger.error(f"Outbox cleanup failed: {e}")


def cleanup_expired_carts():
    """Deactivate carts whose active session has exceeded the sliding TTL.

    Uses updated_at as the sliding window anchor. Carts deactivated here are
    counted in metrics.cart_expired_total when prometheus is available.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=CART_TTL_DAYS)
        repo = _carts_repo()
        expired = []
        for row in repo.find_all({"status": "active"}, limit=None):
            updated = row.get("updated_at")
            if isinstance(updated, str):
                try:
                    updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if updated and updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated and updated < cutoff:
                expired.append(row)
        if not expired:
            return 0
        now = datetime.now(timezone.utc)
        for row in expired:
            repo.update({"id": row["id"]}, {"status": "expired", "updated_at": now})
        try:
            from services.metrics import cart_expired_total
            cart_expired_total.labels(user_type="b2c").inc(len(expired))
        except Exception:
            logger.debug("METRICS_UPDATE_SKIPPED | cart_expired_total", exc_info=True)
        logger.info(f"Expired {len(expired)} idle carts")
        return len(expired)
    except Exception as e:
        logger.error(f"Cart TTL cleanup failed: {e}")
        return 0


def cleanup_expired_checkouts():
    """Mark expired checkout sessions as abandoned."""
    try:
        repo = _checkout_repo()
        now = datetime.now(timezone.utc)
        count = 0
        terminal = {"completed", "abandoned", "failed"}
        for row in repo.find_all({}, limit=None):
            state = (row.get("state") or row.get("status") or "").lower()
            if state in terminal:
                continue
            expires = row.get("expires_at")
            if isinstance(expires, str):
                try:
                    expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if expires and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires and expires < now:
                updates = {"updated_at": now}
                if "state" in row or row.get("state") is not None:
                    updates["state"] = "abandoned"
                else:
                    updates["status"] = "abandoned"
                if repo.update({"id": row["id"]}, updates):
                    count += 1
        if count:
            logger.info(f"Abandoned {count} expired checkout sessions")
        return count
    except Exception as e:
        logger.error(f"Checkout TTL cleanup failed: {e}")
        return 0


def run_all():
    cleanup_dedup_table()
    cleanup_outbox()
    cleanup_expired_carts()
    cleanup_expired_checkouts()


if __name__ == "__main__":
    run_all()