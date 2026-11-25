"""Resolve inbound WhatsApp traffic by business phone → tenants.waba_phone_id.

Bindings live in the tenants table only (admin / DB). There is no Active Test
Tenant override and no hardcoded phone→tenant map in code.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .defaults import DEFAULT_TENANT_ID

logger = logging.getLogger("tenancy.resolver")


def _extract_phone_ids(payload: Dict[str, Any]) -> list[str]:
    """All plausible phone-number identifiers in a WABA webhook, best first."""
    out: list[str] = []
    try:
        entry = (payload.get("entry") or [{}])[0] or {}
        changes = (entry.get("changes") or [{}])[0] or {}
        value = changes.get("value") or {}

        raw = entry.get("id")
        if raw not in (None, ""):
            out.append(str(raw))

        meta = value.get("metadata") or {}
        for key in ("phone_number_id", "display_phone_number", "display_phone_number_id"):
            val = meta.get(key)
            if val not in (None, ""):
                out.append(str(val))
    except (AttributeError, IndexError, TypeError) as exc:
        logger.debug("Could not extract phone ids from payload: %s", exc)
    return out


def active_test_tenant_id() -> Optional[str]:
    """Deprecated: Active Test Tenant override removed. Always None."""
    return None


def canonical_tenant_id(tenant_id: Optional[str]) -> Optional[str]:
    """Map id / slug / display aliases to the tenant registry slug (or id)."""
    raw = str(tenant_id or "").strip()
    if not raw:
        return None
    from . import store

    rec = store.get_tenant(raw)
    if rec:
        return str(rec.get("slug") or rec.get("id") or raw)
    return raw


def _registered_active_tenant(tenant_id: Optional[str]) -> Optional[str]:
    """Return a canonical tenant id only when it is registered and active."""
    candidate = canonical_tenant_id(tenant_id)
    if not candidate:
        return None
    from . import store

    record = store.get_tenant(candidate)
    if not record or str(record.get("status") or "active").strip().lower() != "active":
        return None
    return str(record.get("slug") or record.get("id") or candidate)


def resolve_effective_tenant_id(
    wa_id: str = "",
    tenant_id: Optional[str] = None,
    *,
    allow_test_override: bool = True,
) -> Optional[str]:
    """Which tenant profile handles this message.

    Order:
      1. Explicit hint (webhook phone binding, simulator, caller)
      2. ``user_states.tenant_id`` for this ``wa_id``

    ``allow_test_override`` is ignored (kept for call-site compatibility).
    """
    del allow_test_override  # override removed — phone / hint routing only
    hint = _registered_active_tenant(tenant_id)
    if hint:
        return hint

    return resolve_tenant_for_user(wa_id, allow_test_override=False)


def resolve_tenant_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Resolve inbound WABA webhook → tenant via ``tenants.waba_phone_id``."""
    for phone_id in _extract_phone_ids(payload or {}):
        active_tenant = resolve_tenant_for_phone(
            phone_id,
            allow_test_override=False,
        )
        if active_tenant:
            logger.debug(
                "Resolved active tenant %s from phone id %s", active_tenant, phone_id,
            )
            return active_tenant

    for candidate in _extract_phone_ids(payload or {}):
        active_tenant = _registered_active_tenant(candidate)
        if active_tenant:
            return active_tenant

    phones = _extract_phone_ids(payload or {})
    if phones:
        logger.warning(
            "Unbound or inactive WABA phone id(s) %s — ignoring inbound message",
            phones,
        )
    return None


def resolve_tenant_for_phone(
    phone_id: str,
    *,
    allow_test_override: bool = True,
) -> Optional[str]:
    """Resolve ``tenants.waba_phone_id``; unknown or inactive numbers return None."""
    del allow_test_override
    from . import store

    raw_phone_id = str(phone_id or "").strip()
    candidates = [raw_phone_id] if raw_phone_id else []
    try:
        normalized = store.normalize_waba_phone_id(raw_phone_id)
        if normalized not in candidates:
            candidates.append(normalized)
    except ValueError:
        logger.debug("PHONE_ID_NORMALIZE_SKIPPED | phone_id=%s", raw_phone_id, exc_info=True)
    for candidate in candidates:
        tid = store.find_tenant_by_phone_id(candidate)
        if tid:
            active_tenant = _registered_active_tenant(tid)
            if active_tenant:
                return active_tenant
    return None


def bind_phone_id(tenant_id: str, phone_id: str) -> bool:
    """Register a WABA phone-id for a tenant. Idempotent."""
    from . import store

    return store.set_waba_phone_id(tenant_id, phone_id)


def resolve_default_tenant() -> Optional[str]:
    """Fallback tenant when no phone binding applies.

    Order:
      1. ``DEFAULT_TENANT_ID`` from the environment, if registered and active
      2. the single active tenant, when exactly one is registered
    """
    from . import store

    configured = os.getenv("DEFAULT_TENANT_ID", "").strip()
    if configured and configured != "default" and store.get_tenant(configured):
        return configured

    active = [t for t in store.list_tenants(status="active") if t.get("id")]
    if len(active) == 1:
        return str(active[0].get("slug") or active[0]["id"])
    return None


def resolve_tenant_for_user(
    wa_id: str,
    *,
    allow_test_override: bool = True,
) -> Optional[str]:
    """Tenant stamped on this WhatsApp user, if still registered and active."""
    del allow_test_override
    if not wa_id:
        return None

    from . import store

    tid = store.tenant_id_for_user(wa_id)
    if tid:
        active_tenant = _registered_active_tenant(tid)
        if active_tenant:
            return active_tenant
        logger.warning(
            "user %s is stamped with unregistered or inactive tenant %r; ignoring message",
            wa_id, tid,
        )

    return None
