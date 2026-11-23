import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from database import get_db_context

logger = logging.getLogger(__name__)

TABLE_NAME = "google_oauth_tokens"
TOKEN_PREFIX = "fernet:v1:"


def _fernet():
    key = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required for Google token storage")
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc


def _seal(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    return TOKEN_PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _open(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if not value.startswith(TOKEN_PREFIX):
        # Legacy rows are accepted only when the encryption key is configured;
        # the caller immediately re-encrypts them.
        _fernet()
        return value
    return _fernet().decrypt(value[len(TOKEN_PREFIX):].encode("ascii")).decode("utf-8")


def _use_mongodb():
    from db.core import use_mongodb
    return use_mongodb()


def _ensure_table():
    if _use_mongodb():
        return
    with get_db_context() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                tenant_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at INTEGER NOT NULL,
                token_type TEXT,
                scope TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{TABLE_NAME}_tenant ON {TABLE_NAME}(tenant_id)"
        )


_ensure_table()


def save_token(
    tenant_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: int = 0,
    token_type: Optional[str] = None,
    scope: Optional[str] = None,
) -> bool:
    """Store or update the OAuth token for a tenant.
    expires_at should be a unix timestamp (seconds since epoch) in UTC.
    """
    try:
        updated = datetime.now(timezone.utc)
        if _use_mongodb():
            from db.mongo import Repository
            Repository(TABLE_NAME).upsert(
                {"tenant_id": tenant_id},
                {
                    "tenant_id": tenant_id,
                    "access_token": _seal(access_token),
                    "refresh_token": _seal(refresh_token),
                    "expires_at": expires_at,
                    "token_type": token_type,
                    "scope": scope,
                    "updated_at": updated,
                },
            )
            return True
        with get_db_context() as conn:
            conn.execute(
                f"""
                INSERT INTO {TABLE_NAME} (tenant_id, access_token, refresh_token, expires_at, token_type, scope, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    expires_at=excluded.expires_at,
                    token_type=excluded.token_type,
                    scope=excluded.scope,
                    updated_at=excluded.updated_at
                """,
                (
                    tenant_id,
                    _seal(access_token),
                    _seal(refresh_token),
                    expires_at,
                    token_type,
                    scope,
                    updated.isoformat(),
                ),
            )
        return True
    except Exception as e:
        logger.error(f"Failed to save Google OAuth token for tenant {tenant_id}: {e}")
        return False


def get_token(tenant_id: str) -> Optional[dict]:
    """Retrieve stored token info for a tenant. Returns dict or None."""
    try:
        if _use_mongodb():
            from db.mongo import Repository
            row = Repository(TABLE_NAME).find_one({"tenant_id": tenant_id})
            if row:
                token = {
                    "access_token": _open(row["access_token"]),
                    "refresh_token": _open(row.get("refresh_token")),
                    "expires_at": row["expires_at"],
                    "token_type": row.get("token_type"),
                    "scope": row.get("scope"),
                }
                if not str(row.get("access_token") or "").startswith(TOKEN_PREFIX):
                    save_token(tenant_id=tenant_id, **token)
                return token
            return None
        with get_db_context() as conn:
            row = conn.execute(
                f"SELECT access_token, refresh_token, expires_at, token_type, scope FROM {TABLE_NAME} WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            if row:
                token = {
                    "access_token": _open(row["access_token"]),
                    "refresh_token": _open(row["refresh_token"]),
                    "expires_at": row["expires_at"],
                    "token_type": row["token_type"],
                    "scope": row["scope"],
                }
                if not str(row["access_token"] or "").startswith(TOKEN_PREFIX):
                    save_token(tenant_id=tenant_id, **token)
                return token
    except Exception as e:
        logger.error(f"Failed to load Google OAuth token for tenant {tenant_id}: {e}")
    return None


def delete_token(tenant_id: str) -> bool:
    """Delete stored OAuth token for a tenant."""
    try:
        if _use_mongodb():
            from db.mongo import Repository
            Repository(TABLE_NAME).delete_one({"tenant_id": tenant_id})
            return True
        with get_db_context() as conn:
            conn.execute(f"DELETE FROM {TABLE_NAME} WHERE tenant_id = ?", (tenant_id,))
        return True
    except Exception as e:
        logger.error(f"Failed to delete Google OAuth token for tenant {tenant_id}: {e}")
        return False
