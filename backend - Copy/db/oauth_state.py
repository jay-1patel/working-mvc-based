"""Single-use, tenant-bound OAuth state persistence."""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timezone

from .core import get_db_context, use_mongodb

TABLE = "google_oauth_states"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ensure_sqlite() -> None:
    with get_db_context() as conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {TABLE} (
                state_hash TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                session_hash TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL
            )"""
        )
        conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_expires ON {TABLE}(expires_at)")


def create_oauth_state(tenant_id: str, session_id: str, redirect_uri: str, ttl_seconds: int = 600) -> str:
    raw = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    expires_at = int(time.time()) + ttl_seconds
    values = {
        "state_hash": _hash(raw),
        "tenant_id": str(tenant_id),
        "session_hash": _hash(session_id),
        "redirect_uri": redirect_uri,
        "expires_at": expires_at,
        "created_at": now,
    }
    if use_mongodb():
        from .mongo import get_database

        collection = get_database()[TABLE]
        collection.create_index("state_hash", unique=True)
        collection.insert_one(values)
    else:
        _ensure_sqlite()
        with get_db_context() as conn:
            conn.execute(
                f"""INSERT INTO {TABLE}
                (state_hash, tenant_id, session_hash, redirect_uri, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                tuple(values[key] for key in ("state_hash", "tenant_id", "session_hash", "redirect_uri", "expires_at", "created_at")),
            )
    return raw


def consume_oauth_state(raw_state: str, redirect_uri: str) -> dict | None:
    if not raw_state:
        return None
    state_hash = _hash(raw_state)
    now = int(time.time())
    if use_mongodb():
        from .mongo import get_database

        row = get_database()[TABLE].find_one_and_update(
            {"state_hash": state_hash, "redirect_uri": redirect_uri, "expires_at": {"$gt": now}, "used_at": {"$exists": False}},
            {"$set": {"used_at": datetime.now(timezone.utc)}},
        )
        return dict(row) if row else None
    _ensure_sqlite()
    with get_db_context() as conn:
        row = conn.execute(
            f"SELECT * FROM {TABLE} WHERE state_hash = ? AND redirect_uri = ? AND expires_at > ? AND used_at IS NULL",
            (state_hash, redirect_uri, now),
        ).fetchone()
        if not row:
            return None
        updated = conn.execute(
            f"UPDATE {TABLE} SET used_at = ? WHERE state_hash = ? AND used_at IS NULL",
            (datetime.now(timezone.utc).isoformat(), state_hash),
        )
        if updated.rowcount != 1:
            return None
        return dict(row)

