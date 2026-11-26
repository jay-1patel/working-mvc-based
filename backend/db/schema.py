"""Schema bootstrap — MongoDB only (legacy SQLite DDL removed)."""
import os

from .core import logger


def init_db():
    from datetime import datetime, timezone

    from .mongo import REGISTRY, get_database, initialize_indexes, require_replica_set

    database = get_database()
    require_replica_set(database)
    initialize_indexes(database)
    database["_app_meta"].update_one(
        {"_id": "schema"},
        {
            "$setOnInsert": {
                "version": REGISTRY["version"],
                "mode": "fresh",
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    logger.info(
        "MongoDB schema indexes ready | collections=%s", len(REGISTRY["tables"])
    )
    try:
        from .privileges import ensure_menu_privilege_catalog

        ensure_menu_privilege_catalog()
        logger.info("Seeded menu_privilege catalog (superadmin skips grant checks)")
    except Exception:
        logger.debug("menu privilege seed skipped", exc_info=True)


def _default_tenant_id() -> str:
    try:
        from shared.tenancy.resolver import resolve_default_tenant

        return resolve_default_tenant()
    except Exception:
        return os.environ.get("DEFAULT_TENANT_ID", "default")


def _noop_sqlite_migration(*_args, **_kwargs):
    """Legacy SQLite migration hooks — no-ops under MongoDB-only."""


# Re-exported names kept for `from database import …` compatibility.
_has_legacy_unique_on_phone_id = lambda conn: False
_rebuild_tenants_for_partial_unique = _noop_sqlite_migration
_init_tenancy_tables = _noop_sqlite_migration
_default_tenant_id_for_conn = lambda conn: _default_tenant_id()
_init_embedding_tenancy = _noop_sqlite_migration
_has_legacy_global_unique_on_slug = lambda conn: False
_table_pk_columns = lambda conn, table: []
_migrate_composite_tenant_wa_keys = _noop_sqlite_migration
_init_api_onboarding_tables = _noop_sqlite_migration
_init_tenant_change_tables = _noop_sqlite_migration
_ensure_callback_tables = _noop_sqlite_migration
_init_integration_tables = _noop_sqlite_migration
_init_lead_tables = _noop_sqlite_migration
_init_offerings_migration = _noop_sqlite_migration
_migrate_products_per_tenant_slug = _noop_sqlite_migration
_init_record_columns_table = _noop_sqlite_migration
_init_conversation_state_columns = _noop_sqlite_migration