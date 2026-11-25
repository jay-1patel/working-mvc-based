"""Key/value app settings and the active test tenant data access — extracted from backend/database.py."""
from datetime import datetime, timezone
from typing import Optional

from .core import logger, get_db_context, use_mongodb


def get_app_setting(key: str, default: str = "") -> str:
    try:
        if use_mongodb():
            from .mongo import Repository
            row = Repository("app_settings").find_one({"key": key})
            return row["value"] if row and row.get("value") is not None else default
        with get_db_context() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS app_settings (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row and row["value"] is not None else default
    except Exception as e:
        logger.debug(f"get_app_setting error for key {key}: {e}")
        return default


def set_app_setting(key: str, value: str) -> None:
    if use_mongodb():
        from .mongo import Repository
        Repository("app_settings").upsert(
            {"key": key},
            {
                "key": key,
                "value": str(value or ""),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        return
    with get_db_context() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS app_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
            (key, str(value or "")),
        )


def get_active_test_tenant() -> Optional[str]:
    """Deprecated: phone→tenant routing only; override always off."""
    return None


def set_active_test_tenant(tenant_id: Optional[str]) -> None:
    """Deprecated no-op: Active Test Tenant override removed.

    Clears any leftover ``app_settings.active_test_tenant`` so old values
    cannot linger. Routing uses ``tenants.waba_phone_id`` only.
    """
    del tenant_id
    try:
        set_app_setting("active_test_tenant", "")
    except Exception:
        logger.debug("ACTIVE_TEST_TENANT_CLEAR_SKIPPED", exc_info=True)
    logger.info(
        "ACTIVE_TEST_TENANT_DISABLED | routing uses tenants.waba_phone_id only"
    )
