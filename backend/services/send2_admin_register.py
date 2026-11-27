"""Signup: store Send2 username + id + password into ``admins``.

1. Optionally POST credentials to Send2 (SEND2_LOGIN_API_URL).
2. Create a unique ``tenant_id`` (or reuse the admin's existing one).
3. Upsert ``admins`` with ``id`` as ``admins.id`` (chatbot PK).
4. Encrypt password with CREDENTIAL_MASTER_KEY (AES-GCM) into ``admins.password_hash``
   and into the Send2 vault.
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any

import httpx

from core.send2_auth import encode_send2_username, normalize_login_username
from database import (
    create_admin as db_create_admin,
    get_admin_by_id,
    get_admin_by_username,
    update_admin as db_update_admin,
)

# Signup stores username in plain form (e.g. "japan"). Legacy Base64 rows
# remain readable via admin_username_candidates.

logger = logging.getLogger("send2_admin_register")


class Send2RegisterError(RuntimeError):
    """User-facing register failure (invalid input or Send2 rejection)."""


def _encrypt_password(password: str, *, tenant_id: str, admin_id: int) -> str:
    """AES-GCM seal with CREDENTIAL_MASTER_KEY. Returns ciphertext_b64."""
    from services.credential_vault import encrypt_value

    return encrypt_value(str(password), str(tenant_id), str(admin_id))


def decrypt_admin_password(
    password_hash: str,
    *,
    tenant_id: str,
    admin_id: int,
) -> str:
    """Decrypt an AES-GCM ``admins.password_hash`` sealed at signup."""
    from services.credential_vault import decrypt_value

    return decrypt_value(str(password_hash or ""), str(tenant_id), str(admin_id))


def _login_api_url() -> str:
    return (os.getenv("SEND2_LOGIN_API_URL") or "").strip()


def _parse_admin_id(raw: Any) -> int:
    """``id`` from Send2 is the chatbot ``admins.id`` (e.g. 3042)."""
    text = str(raw or "").strip()
    if not text:
        raise Send2RegisterError("id is required")
    try:
        admin_id = int(text)
    except (TypeError, ValueError) as exc:
        raise Send2RegisterError("id must be a numeric admins.id") from exc
    if admin_id <= 0:
        raise Send2RegisterError("id must be a positive integer")
    return admin_id


def _allocate_tenant_id() -> str:
    """Auto-generate a short unique tenant_id (12 hex chars)."""
    from shared.tenancy import store as tenancy_store

    for _ in range(8):
        # 12 chars — short enough for panel/paths, still unique with retry.
        candidate = secrets.token_hex(6)
        if not tenancy_store.find_registry_conflict(candidate, candidate):
            return candidate
    raise Send2RegisterError("Could not allocate a unique tenant_id")


def _ensure_signup_tenant(tenant_id: str, *, username: str) -> str:
    """Create/refresh the tenant shell for this signup."""
    from shared.tenancy import store as tenancy_store

    tenancy_store.ensure_tenant(
        tenant_id,
        slug=tenant_id,
        vertical="generic",
        display_name=username,
        status="active",
    )
    return tenant_id


def _store_encrypted_password(
    *,
    tenant_id: str,
    admin_id: int,
    username: str,
    password: str,
) -> None:
    """AES-GCM encrypt password with CREDENTIAL_MASTER_KEY into send2_credentials.

    Vault AAD uses ``tenant_id`` + ``str(admin_id)`` (admins.id as binding key,
    not krt_unique_id on the admin row).
    """
    from services.credential_vault import store_send2_credentials

    store_send2_credentials(
        tenant_id=tenant_id,
        krt_unique_id=str(admin_id),
        username=username,
        password=password,
        extra={"source": "signup", "admins_id": admin_id},
    )


def call_send2_login_api(username: str, admin_id: str, password: str) -> dict[str, Any]:
    """POST credentials to Send2. Raises Send2RegisterError on failure.

    When ``SEND2_LOGIN_API_URL`` is unset, skip the remote call (local/dev)
    and return ``{"skipped": True}`` so storage can still be tested.
    """
    url = _login_api_url()
    if not url:
        logger.warning("SEND2_LOGIN_API_URL unset — skipping remote Send2 call")
        return {"skipped": True, "ok": True}

    payload = {
        "username": username,
        "password": password,
        "id": admin_id,
        "customerid": admin_id,
        "customer_id": admin_id,
    }
    timeout = float(os.getenv("SEND2_LOGIN_API_TIMEOUT") or "30")
    try:
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            response = client.post(url, json=payload)
    except Exception as exc:
        logger.error("SEND2_LOGIN_API_REQUEST_FAILED | error=%s", type(exc).__name__)
        raise Send2RegisterError("Send2 login API request failed") from exc

    if response.status_code >= 400:
        logger.error(
            "SEND2_LOGIN_API_REJECTED | status=%s",
            response.status_code,
        )
        raise Send2RegisterError(
            f"Send2 login API rejected credentials (HTTP {response.status_code})"
        )

    body: Any = None
    try:
        body = response.json()
    except Exception:
        body = {"raw": (response.text or "")[:200]}

    # Common failure shapes from CPaaS panels — treat as auth failure.
    if isinstance(body, dict):
        status_val = str(body.get("status") or body.get("Status") or "").strip().lower()
        if status_val in {"error", "fail", "failed", "invalid"}:
            raise Send2RegisterError("Send2 login API rejected credentials")
        ok_val = body.get("ok")
        if ok_val is False:
            raise Send2RegisterError("Send2 login API rejected credentials")

    return {"skipped": False, "ok": True, "http_status": response.status_code}


def _resolve_signup_tenant_id(
    *,
    existing_admin: dict | None,
    requested_tenant_id: str | None,
) -> str:
    """Pick tenant for this signup.

    Priority:
      1. Admin already bound → keep that tenant (stable identity).
      2. Caller passed ``tenant_id`` → must already exist (link same company).
      3. Else auto-generate a short unique tenant_id.
    """
    from shared.tenancy import store as tenancy_store

    already = str((existing_admin or {}).get("tenant_id") or "").strip()
    if already:
        return already

    requested = str(requested_tenant_id or "").strip()
    if requested:
        if not tenancy_store.get_tenant(requested):
            raise Send2RegisterError(f"tenant_id '{requested}' does not exist")
        return requested

    return _allocate_tenant_id()


def register_send2_admin(
    *,
    username: str,
    customer_id: str,
    password: str,
    role: str = "admin",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Validate with Send2 (when configured), create/link tenant, upsert admin, encrypt password.

    ``customer_id`` is the request field ``id`` — the chatbot admin primary key
    (e.g. 3042), not ``krt_unique_id``.

    Pass ``tenant_id`` to attach this admin to an existing company tenant;
    omit it to auto-create a new one.
    """
    try:
        plain_username = normalize_login_username(username)
    except ValueError as exc:
        raise Send2RegisterError(str(exc) or "Invalid username") from exc

    admin_id = _parse_admin_id(customer_id)
    plain_password = str(password or "")
    if not plain_password:
        raise Send2RegisterError("password is required")

    send2_result = call_send2_login_api(plain_username, str(admin_id), plain_password)

    # Store username exactly as provided (plain), not Base64.
    stored_username = plain_username
    legacy_username = encode_send2_username(plain_username)
    session_id = secrets.token_urlsafe(32)

    existing = get_admin_by_id(admin_id)
    by_username = (
        get_admin_by_username(stored_username)
        or get_admin_by_username(legacy_username)
    )
    if by_username and int(by_username.get("id") or 0) != admin_id:
        raise Send2RegisterError(
            f"username '{plain_username}' is already used by admins.id={by_username.get('id')}"
        )

    tenant_id = _resolve_signup_tenant_id(
        existing_admin=existing,
        requested_tenant_id=tenant_id,
    )
    _ensure_signup_tenant(tenant_id, username=plain_username)

    try:
        password_hash = _encrypt_password(
            plain_password, tenant_id=tenant_id, admin_id=admin_id
        )
    except Exception as exc:
        logger.exception(
            "SIGNUP_PASSWORD_ENCRYPT_FAILED | admins.id=%s | tenant=%s",
            admin_id,
            tenant_id,
        )
        raise Send2RegisterError("Failed to encrypt password") from exc

    if existing:
        target_username = str(existing.get("username") or stored_username)
        updated = db_update_admin(
            target_username,
            admin_id=admin_id,
            username=stored_username,
            password_hash=password_hash,
            salt="",
            session_id=session_id,
            tenant_id=tenant_id,
        )
        if not updated:
            raise Send2RegisterError("Failed to update admin record")
        action = "updated"
        result_role = existing.get("role") or role
    else:
        try:
            created_id = db_create_admin(
                stored_username,
                password_hash=password_hash,
                salt="",
                role=role,
                permissions={},
                session_id=session_id,
                tenant_id=tenant_id,
                admin_id=admin_id,
            )
        except Exception as exc:
            # Duplicate id / username unique index, or other store error.
            raise Send2RegisterError(
                f"Failed to create admin with id={admin_id}: {exc}"
            ) from exc
        if int(created_id) != admin_id:
            raise Send2RegisterError(
                f"Created admin id mismatch: expected {admin_id}, got {created_id}"
            )
        action = "created"
        result_role = role

    try:
        _store_encrypted_password(
            tenant_id=tenant_id,
            admin_id=admin_id,
            username=plain_username,
            password=plain_password,
        )
    except Exception as exc:
        logger.exception("SIGNUP_VAULT_STORE_FAILED | admins.id=%s | tenant=%s", admin_id, tenant_id)
        raise Send2RegisterError("Failed to encrypt and store password") from exc

    # No menu privileges on signup — including setup_chatbot / onboarding.
    # Super admin must grant privileges before the admin can set up the chatbot.

    # Never log password / hash material.
    logger.info(
        "SIGNUP_%s | admins.id=%s | username=%s | tenant=%s | send2_skipped=%s",
        action.upper(),
        admin_id,
        plain_username,
        tenant_id,
        bool(send2_result.get("skipped")),
    )
    return {
        "status": "ok",
        "action": action,
        "user_id": admin_id,
        "id": admin_id,
        "username": plain_username,
        "tenant_id": tenant_id,
        "session_id": session_id,
        "role": result_role,
        "send2_validated": not bool(send2_result.get("skipped")),
    }
