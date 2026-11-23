"""Admin/audit event logging data access — extracted from backend/database.py."""
import json
import re
from datetime import datetime, timedelta, timezone

from .core import (
    logger, get_db_context, use_mongodb, _ensure_columns,
    _audit_request_context, _facade_ref,
)


def _init_admin_audit_tables(conn):
    """Create the durable, append-only admin audit log retained for one year."""
    if conn is None or use_mongodb():
        return
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            actor_id INTEGER,
            actor_username TEXT,
            actor_role TEXT,
            action TEXT NOT NULL,
            outcome TEXT NOT NULL DEFAULT 'success' CHECK (outcome IN ('success', 'failure')),
            resource_type TEXT NOT NULL DEFAULT '',
            resource_id TEXT NOT NULL DEFAULT '',
            target_username TEXT,
            tenant_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT,
            user_agent TEXT,
            tenant_name TEXT,
            tenant_slug TEXT,
            actor_kind TEXT NOT NULL DEFAULT 'admin',
            actor_label TEXT
        )"""
    )
    _ensure_columns(conn, "admin_audit_events", [
        ("ip_address", "TEXT"),
        ("user_agent", "TEXT"),
        ("tenant_name", "TEXT"),
        ("tenant_slug", "TEXT"),
        ("actor_kind", "TEXT NOT NULL DEFAULT 'admin'"),
        ("actor_label", "TEXT"),
    ])
    conn.execute("CREATE INDEX IF NOT EXISTS ix_admin_audit_created ON admin_audit_events(created_at DESC, id DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_admin_audit_actor ON admin_audit_events(actor_username, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_admin_audit_action ON admin_audit_events(action, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_admin_audit_tenant ON admin_audit_events(tenant_id, created_at DESC)")
    conn.execute("DELETE FROM admin_audit_events WHERE datetime(created_at) < datetime('now', '-365 days')")
    
    # Initialize new audit_logs table
    _init_audit_logs_table(conn)


_AUDIT_SENSITIVE_KEY_PARTS = (
    "password", "otp", "token", "secret", "credential", "authorization", "api_key", "payload",
    "file_path", "filepath", "local_path", "media_url", "detail_url", "signed_url", "upload_url", "url",
)


def safe_audit_details(value):
    """Remove secrets and deployment paths/URLs recursively before storing or returning details."""
    if isinstance(value, dict):
        return {
            str(key): safe_audit_details(item)
            for key, item in value.items()
            if not any(part in str(key).lower().replace('-', '_') for part in _AUDIT_SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:[\\\\/]", text):
            return "[redacted path]"
        if re.search(r"https?://", text, flags=re.IGNORECASE):
            return "[redacted URL]"
        return text[:1000]
    if isinstance(value, (list, tuple)):
        return [safe_audit_details(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def record_admin_audit_event(
    conn,
    *,
    action: str,
    actor: dict | None = None,
    outcome: str = "success",
    resource_type: str = "",
    resource_id: str | int | None = None,
    target_username: str | None = None,
    tenant_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    tenant_name: str | None = None,
    tenant_slug: str | None = None,
    actor_kind: str | None = None,
    actor_label: str | None = None,
) -> int:
    """Record an audit event using the caller's transaction (or Mongo Repository)."""
    if outcome not in {"success", "failure"}:
        raise ValueError("Audit outcome must be success or failure")
    actor = actor or {}
    context = _audit_request_context.get() or {}
    tenant_id = tenant_id or actor.get("tenant_id")
    mongo_mode = use_mongodb() or conn is None

    if tenant_id and (tenant_name is None or tenant_slug is None):
        try:
            if mongo_mode:
                from .mongo import Repository
                tenant = Repository("tenants").find_one({"id": str(tenant_id)})
                if tenant:
                    tenant_name = tenant_name or tenant.get("display_name") or None
                    tenant_slug = tenant_slug or tenant.get("slug") or None
            else:
                tenant = conn.execute(
                    "SELECT display_name, slug FROM tenants WHERE id = ?",
                    (str(tenant_id),),
                ).fetchone()
                if tenant:
                    tenant_name = tenant_name or tenant["display_name"] or None
                    tenant_slug = tenant_slug or tenant["slug"] or None
        except Exception:
            # Compatibility with audit tests/older database fixtures without
            # the tenant registry table.
            logger.debug("AUDIT_TENANT_LOOKUP_SKIPPED | tenant=%s", tenant_id, exc_info=True)
    actor_kind = actor_kind or actor.get("type") or ("tenant_token" if actor.get("token_id") else "admin")
    actor_label = actor_label or actor.get("label") or actor.get("username")
    details_payload = _facade_ref("safe_audit_details", safe_audit_details)(details or {})
    created_at = datetime.now(timezone.utc)

    if mongo_mode:
        from .mongo import Repository
        try:
            cutoff = created_at - timedelta(days=365)
            Repository("admin_audit_events").delete_many({"created_at": {"$lt": cutoff}})
        except Exception:
            logger.debug("AUDIT_RETENTION_CLEANUP_SKIPPED", exc_info=True)
        row = Repository("admin_audit_events").insert({
            "created_at": created_at,
            "actor_id": actor.get("id"),
            "actor_username": actor.get("username"),
            "actor_role": actor.get("role"),
            "action": action,
            "outcome": outcome,
            "resource_type": resource_type,
            "resource_id": "" if resource_id is None else str(resource_id),
            "target_username": target_username,
            "tenant_id": tenant_id,
            "details_json": details_payload,
            "ip_address": ip_address or context.get("ip_address"),
            "user_agent": (user_agent or context.get("user_agent") or "")[:512] or None,
            "tenant_name": tenant_name,
            "tenant_slug": tenant_slug,
            "actor_kind": actor_kind,
            "actor_label": actor_label,
        })
        return int(row["id"])

    try:
        _init_admin_audit_tables(conn)
        conn.execute("DELETE FROM admin_audit_events WHERE datetime(created_at) < datetime('now', '-365 days')")
    except Exception:
        # deliberate: retention cleanup is housekeeping — it must never
        # block recording the audit event itself.
        logger.debug("AUDIT_RETENTION_CLEANUP_SKIPPED", exc_info=True)

    cursor = conn.execute(
        """INSERT INTO admin_audit_events
           (created_at, actor_id, actor_username, actor_role, action, outcome,
            resource_type, resource_id, target_username, tenant_id, details_json,
            ip_address, user_agent, tenant_name, tenant_slug, actor_kind, actor_label)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            created_at.isoformat(), actor.get("id"), actor.get("username"),
            actor.get("role"), action, outcome, resource_type,
            "" if resource_id is None else str(resource_id), target_username,
            tenant_id,
            json.dumps(details_payload, ensure_ascii=False),
            ip_address or context.get("ip_address"),
            (user_agent or context.get("user_agent") or "")[:512] or None,
            tenant_name, tenant_slug, actor_kind, actor_label,
        ),
    )
    return int(cursor.lastrowid)


def _init_audit_logs_table(conn):
    """Initialize the dedicated audit_logs table for Healthy Earth theme."""
    if conn is None or use_mongodb():
        return
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failed', 'pending')),
            description TEXT,
            metadata TEXT DEFAULT '{}'
        )"""
    )
    
    # Create indexes for performance
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created ON audit_logs(created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs(actor, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_category ON audit_logs(category, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_status ON audit_logs(status, created_at DESC)")


def record_audit_log_event(
    conn,
    actor: str,
    action: str,
    category: str,
    status: str = "success",
    description: str = "",
    metadata: dict = None
):
    """Record an audit log event for the Healthy Earth audit system."""
    if status not in ("success", "failed", "pending"):
        raise ValueError("Status must be success, failed, or pending")
    
    if use_mongodb() or conn is None:
        from .mongo import Repository
        row = Repository("audit_logs").insert({
            "created_at": datetime.now(timezone.utc),
            "actor": actor,
            "action": action,
            "category": category,
            "status": status,
            "description": description,
            "metadata": metadata or {},
        })
        return int(row.get("id") or 0)

    conn.execute(
        """INSERT INTO audit_logs 
           (created_at, actor, action, category, status, description, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            actor,
            action,
            category,
            status,
            description,
            json.dumps(metadata or {})
        )
    )
    return conn.total_changes
