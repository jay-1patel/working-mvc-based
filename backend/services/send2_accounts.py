"""Shared Send2 CPaaS login + phone→tenant bindings from the tenants table.

One Send2 username/password serves every business number. Routing is only by
``tenants.waba_phone_id``:

  15559227148 → tenant ``c`` (automobile)
  15558072955 → tenant ``spiritual``
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("send2_accounts")

# Canonical bindings for this deployment (idempotent upsert into tenants).
DEFAULT_PHONE_BINDINGS: tuple[tuple[str, str], ...] = (
    ("c", "15559227148"),
    ("spiritual", "15558072955"),
)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def ensure_default_phone_bindings() -> list[dict[str, str]]:
    """Idempotently bind known WABA numbers on tenants ``c`` and ``spiritual``."""
    from shared.tenancy import store as tenancy_store

    applied: list[dict[str, str]] = []
    for tenant_id, phone in DEFAULT_PHONE_BINDINGS:
        tid = str(tenant_id).strip()
        number = _digits(phone)
        if not tid or not number:
            continue
        if not tenancy_store.get_tenant(tid):
            logger.warning(
                "SEND2_BIND_SKIP | tenant=%s missing — create tenant before binding %s",
                tid, number,
            )
            continue
        try:
            tenancy_store.set_waba_phone_id(tid, number)
            applied.append({"tenant_id": tid, "waba_phone_id": number})
            logger.info("SEND2_BIND_OK | tenant=%s | number=%s", tid, number)
        except Exception:
            logger.exception("SEND2_BIND_FAILED | tenant=%s | number=%s", tid, number)
    return applied


def shared_send2_credentials() -> Optional[tuple[str, str]]:
    """Single CPaaS login from env (used for every tenant / number)."""
    from routing.config import SEND2_PASSWORD, SEND2_USERNAME

    user = (SEND2_USERNAME or "").strip()
    password = (SEND2_PASSWORD or "").strip()
    if user and password:
        return user, password
    return None


def resolve_account_credentials(tenant_id: str) -> Optional[tuple[str, str]]:
    """Vault (optional) → shared SEND2_USERNAME / SEND2_PASSWORD."""
    tid = str(tenant_id or "").strip()
    if tid:
        try:
            try:
                from services.credential_vault import get_send2_credentials, has_vault_record
            except ImportError:
                from backend.services.credential_vault import (
                    get_send2_credentials,
                    has_vault_record,
                )
            if has_vault_record(tid):
                creds = get_send2_credentials(tid)
                return str(creds["username"]), str(creds["password"])
        except Exception:
            logger.debug("SEND2_VAULT_SKIP | tenant=%s", tid, exc_info=True)
    return shared_send2_credentials()


def list_bound_business_numbers() -> list[dict[str, str]]:
    """Active tenants that have a ``waba_phone_id`` (for logging / diagnostics)."""
    from shared.tenancy import store as tenancy_store

    out: list[dict[str, str]] = []
    try:
        rows = tenancy_store.list_tenants(status="active") or []
    except Exception:
        logger.exception("SEND2_LIST_TENANTS_FAILED")
        return out
    for row in rows:
        tid = str(row.get("slug") or row.get("id") or "").strip()
        number = _digits(row.get("waba_phone_id") or "")
        if tid and number:
            out.append({"tenant_id": tid, "number": number})
    return out


def list_poll_accounts() -> list[dict[str, Any]]:
    """One shared Send2 login — poll once; route each inbound by business number."""
    creds = shared_send2_credentials()
    if not creds:
        logger.warning("SEND2_POLL_SKIP | SEND2_USERNAME/PASSWORD not set")
        return []
    username, password = creds
    return [{
        "tenant_id": "",  # resolved per message from tenants.waba_phone_id
        "number": "",
        "username": username,
        "password": password,
        "shared": True,
    }]


def business_number_from_poll_message(msg: dict) -> str:
    """Best-effort business WhatsApp number that received this Send2 poll row."""
    if not isinstance(msg, dict):
        return ""
    for key in (
        "Receiver",
        "receiver",
        "To",
        "to",
        "ToNumber",
        "to_number",
        "BusinessNumber",
        "business_number",
        "WhatsAppNumber",
        "whatsapp_number",
        "WabaNumber",
        "waba_number",
        "Account",
        "account",
        "display_phone_number",
        "phone_number_id",
    ):
        raw = msg.get(key)
        if raw in (None, ""):
            continue
        digits = _digits(raw)
        if len(digits) >= 10:
            return digits
    return ""
