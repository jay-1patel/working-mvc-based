"""Send2 CPaaS login + phone→tenant bindings from the tenants table.

Credentials come from (in order):
  1. encrypted ``send2_credentials`` vault (per tenant)
  2. ``admins`` table for that tenant (Send2 username Base64 + recoverable password)
  3. optional legacy ``SEND2_USERNAME`` / ``SEND2_PASSWORD`` env only when
     ``SEND2_VAULT_FALLBACK=true``

Routing is by ``tenants.waba_phone_id`` (DB / admin) — never hardcoded here.
"""
from __future__ import annotations

import base64
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("send2_accounts")


def _digits(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _looks_like_hex_digest(value: str) -> bool:
    """True for MD5/SHA-1/SHA-256/etc. hex digests — not usable as Send2 passwords."""
    v = (value or "").strip()
    if len(v) < 32 or len(v) > 128:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in v)


def _recover_send2_password(
    raw: str | None,
    *,
    tenant_id: str | None = None,
    admin_id: int | None = None,
    salt: str | None = None,
) -> str:
    """Recover a Send2 API password from an admins.password / password_hash value.

    Signup rows store AES-GCM ciphertext sealed with CREDENTIAL_MASTER_KEY.
    Legacy Send2-synced rows may still be Base64 or plain. One-way digests
    (MD5/SHA/PBKDF2) cannot be used and are skipped.
    """
    value = str(raw or "").strip()
    if not value or _looks_like_hex_digest(value):
        return ""

    # Prefer AES-GCM decrypt for signup-sealed rows (salt empty / unused).
    # Skip when salt looks like a legacy PBKDF2 random salt.
    salt_val = str(salt or "").strip()
    try_aesgcm = not salt_val or salt_val == "aesgcm"
    if tenant_id and admin_id is not None and try_aesgcm:
        try:
            from services.send2_admin_register import decrypt_admin_password
        except ImportError:
            from backend.services.send2_admin_register import decrypt_admin_password
        try:
            return decrypt_admin_password(
                value,
                tenant_id=str(tenant_id),
                admin_id=int(admin_id),
            )
        except Exception:
            logger.debug("SEND2_ADMINS_AESGCM_DECRYPT_FAILED", exc_info=True)

    # Prefer Base64 → plain (Send2 panel sync style).
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8").strip()
        if (
            decoded
            and not _looks_like_hex_digest(decoded)
            and all(32 <= ord(ch) < 127 for ch in decoded)
        ):
            return decoded
    except Exception:
        pass
    # Plain text stored on the admin row (not a digest).
    if all(32 <= ord(ch) < 127 for ch in value):
        return value
    return ""


def credentials_from_admins(tenant_id: str | None = None) -> Optional[tuple[str, str]]:
    """Load Send2 username/password from the ``admins`` collection.

    Username is stored Base64-encoded (Send2 form). Password is recovered from
    ``password`` / ``password_hash`` when it is Base64 or plain text — never
    when it is only a SHA-256 digest.
    """
    tid = str(tenant_id or "").strip()
    try:
        from db.mongo import Repository
        from core.send2_auth import decode_stored_username
    except ImportError:
        try:
            from backend.db.mongo import Repository
            from backend.core.send2_auth import decode_stored_username
        except ImportError:
            logger.debug("SEND2_ADMINS_IMPORT_SKIP", exc_info=True)
            return None

    filters: dict[str, Any] = {}
    if tid:
        filters["tenant_id"] = tid
    try:
        rows = list(Repository("admins").find(filters, limit=100) or [])
    except Exception:
        logger.exception("SEND2_ADMINS_LOOKUP_FAILED | tenant=%s", tid or "(any)")
        return None

    # Prefer active WhatsApp/AiChatbot admins, then any recoverable row.
    def _score(row: dict) -> tuple:
        services = str(row.get("services") or "").lower()
        flag = str(row.get("flag") if row.get("flag") is not None else "1")
        role = str(row.get("role") or "")
        return (
            0 if flag in ("1", "true", "True") else 1,
            0 if ("whatsapp" in services or "aichatbot" in services) else 1,
            0 if role in ("admin", "super_admin") else 1,
            str(row.get("username") or ""),
        )

    for row in sorted(rows, key=_score):
        plain_user = decode_stored_username(row.get("username"))
        admin_id_raw = row.get("id")
        try:
            admin_id = int(admin_id_raw) if admin_id_raw is not None else None
        except (TypeError, ValueError):
            admin_id = None
        plain_pass = _recover_send2_password(
            row.get("password") if row.get("password") not in (None, "") else row.get("password_hash"),
            tenant_id=str(row.get("tenant_id") or tid or "").strip() or None,
            admin_id=admin_id,
            salt=row.get("salt"),
        )
        if plain_user and plain_pass:
            logger.info(
                "SEND2_CREDS_FROM_ADMINS | tenant=%s | username=%s",
                tid or "(any)",
                plain_user,
            )
            return plain_user, plain_pass

    logger.warning(
        "SEND2_ADMINS_NO_RECOVERABLE_CREDS | tenant=%s | rows=%d",
        tid or "(any)",
        len(rows),
    )
    return None


def shared_send2_credentials() -> Optional[tuple[str, str]]:
    """Shared CPaaS login: admins DB first, optional env only with fallback flag."""
    from_db = credentials_from_admins(None)
    if from_db:
        return from_db

    # Legacy env pair — only when explicitly enabled.
    try:
        from services.credential_vault import vault_fallback_enabled
    except ImportError:
        try:
            from backend.services.credential_vault import vault_fallback_enabled
        except ImportError:
            vault_fallback_enabled = lambda: False  # type: ignore
    if vault_fallback_enabled():
        from routing.config import SEND2_PASSWORD, SEND2_USERNAME
        user = (SEND2_USERNAME or "").strip()
        password = (SEND2_PASSWORD or "").strip()
        if user and password:
            logger.warning("SEND2_VAULT_FALLBACK_USED | prefer admins/vault credentials")
            return user, password
    return None


def resolve_account_credentials(tenant_id: str) -> Optional[tuple[str, str]]:
    """Vault (optional) → admins table for tenant → shared/env fallback."""
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
        from_admins = credentials_from_admins(tid)
        if from_admins:
            return from_admins
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
        logger.warning("SEND2_POLL_SKIP | no Send2 credentials in admins/vault")
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
