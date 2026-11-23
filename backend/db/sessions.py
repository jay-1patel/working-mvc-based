"""24h session-open helpers data access — extracted from backend/database.py."""
from datetime import datetime, timezone
from typing import Optional

from .core import (
    logger, get_db_context, use_mongodb,
    _current_tenant, get_request_tenant
)


def _parse_ts(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            parsed = datetime.strptime(text.replace("Z", "+0000"), fmt.replace("%z", "%z") if "%z" in fmt else fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        return None


def _resolve_tenant_id(wa_id: str, tenant_id: Optional[str] = None) -> Optional[str]:
    tid = (tenant_id or get_request_tenant() or _current_tenant.get() or "").strip()
    if tid:
        return tid
    try:
        if use_mongodb():
            from .mongo import Repository
            row = Repository("user_sessions").find_one({
                "wa_id": wa_id,
                "tenant_id": {"$nin": [None, ""]},
            })
            if row and row.get("tenant_id"):
                return str(row["tenant_id"])
        else:
            with get_db_context() as conn:
                row = conn.execute(
                    "SELECT tenant_id FROM user_sessions WHERE wa_id = ? "
                    "AND tenant_id IS NOT NULL AND TRIM(tenant_id) != '' "
                    "LIMIT 1",
                    (wa_id,),
                ).fetchone()
                if row and row["tenant_id"]:
                    return str(row["tenant_id"])
    except Exception:
        # deliberate: resolver chain — fall through to the next source.
        logger.debug("SESSION_TENANT_RESOLVE_STEP_SKIPPED | source=user_sessions wa=%s", wa_id, exc_info=True)
    try:
        from shared.tenancy.resolver import resolve_default_tenant
        return resolve_default_tenant()
    except Exception:
        import os
        return os.environ.get("DEFAULT_TENANT_ID", "default")


def update_session_inbound(wa_id: str, tenant_id: Optional[str] = None):
    tid = _resolve_tenant_id(wa_id, tenant_id)
    if not tid:
        logger.warning("SESSION_INBOUND_SKIPPED | no tenant for wa=%s", wa_id)
        return
    now = datetime.now(timezone.utc)
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("user_sessions")
        existing = repo.find_one({"tenant_id": tid, "wa_id": wa_id})
        if existing:
            repo.update(
                {"tenant_id": tid, "wa_id": wa_id},
                {"last_inbound_at": now, "session_open": 1},
            )
        else:
            repo.insert({
                "tenant_id": tid,
                "wa_id": wa_id,
                "last_inbound_at": now,
                "session_open": 1,
            })
        return
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO user_sessions (tenant_id, wa_id, last_inbound_at, session_open)
               VALUES (?, ?, CURRENT_TIMESTAMP, 1)
               ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
                 last_inbound_at = CURRENT_TIMESTAMP,
                 session_open = 1""",
            (tid, wa_id),
        )


def update_session_outbound(wa_id: str, tenant_id: Optional[str] = None):
    tid = _resolve_tenant_id(wa_id, tenant_id)
    if not tid:
        logger.warning("SESSION_OUTBOUND_SKIPPED | no tenant for wa=%s", wa_id)
        return
    now = datetime.now(timezone.utc)
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("user_sessions")
        existing = repo.find_one({"tenant_id": tid, "wa_id": wa_id})
        if existing:
            repo.update({"tenant_id": tid, "wa_id": wa_id}, {"last_outbound_at": now})
        else:
            repo.insert({
                "tenant_id": tid,
                "wa_id": wa_id,
                "last_outbound_at": now,
            })
        return
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO user_sessions (tenant_id, wa_id, last_outbound_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
                 last_outbound_at = CURRENT_TIMESTAMP""",
            (tid, wa_id),
        )


def is_session_open(wa_id: str, window_hours: int = 24, tenant_id: Optional[str] = None) -> bool:
    tid = _resolve_tenant_id(wa_id, tenant_id)
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("user_sessions")
        row = repo.find_one({"tenant_id": tid, "wa_id": wa_id})
        if row is None:
            row = repo.find_one({"wa_id": wa_id})
        last_raw = (row or {}).get("last_inbound_at")
    else:
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT last_inbound_at FROM user_sessions WHERE tenant_id = ? AND wa_id = ?",
                (tid, wa_id),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT last_inbound_at FROM user_sessions WHERE wa_id = ? LIMIT 1",
                    (wa_id,),
                ).fetchone()
        last_raw = row["last_inbound_at"] if row else None
    if not last_raw:
        return False
    try:
        last = _parse_ts(last_raw)
        if not last:
            return False
        now = datetime.now(timezone.utc)
        return (now - last).total_seconds() < window_hours * 3600
    except Exception:
        return False


def get_session_info(wa_id: str, tenant_id: Optional[str] = None) -> dict:
    tid = _resolve_tenant_id(wa_id, tenant_id)
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("user_sessions")
        row = repo.find_one({"tenant_id": tid, "wa_id": wa_id})
        if row is None:
            row = repo.find_one({"wa_id": wa_id})
        return dict(row) if row else {}
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM user_sessions WHERE tenant_id = ? AND wa_id = ?",
            (tid, wa_id),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM user_sessions WHERE wa_id = ? LIMIT 1",
                (wa_id,),
            ).fetchone()
    return dict(row) if row else {}
