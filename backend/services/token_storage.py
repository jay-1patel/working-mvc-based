import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from database import get_db_context

logger = logging.getLogger(__name__)

TABLE_NAME = "google_oauth_tokens"


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
                    "access_token": access_token,
                    "refresh_token": refresh_token,
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
                    access_token,
                    refresh_token,
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
                return {
                    "access_token": row["access_token"],
                    "refresh_token": row.get("refresh_token"),
                    "expires_at": row["expires_at"],
                    "token_type": row.get("token_type"),
                    "scope": row.get("scope"),
                }
            return None
        with get_db_context() as conn:
            row = conn.execute(
                f"SELECT access_token, refresh_token, expires_at, token_type, scope FROM {TABLE_NAME} WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            if row:
                return {
                    "access_token": row["access_token"],
                    "refresh_token": row["refresh_token"],
                    "expires_at": row["expires_at"],
                    "token_type": row["token_type"],
                    "scope": row["scope"],
                }
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