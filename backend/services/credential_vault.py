"""Send2 credential vault — encrypt at rest with the platform master key.

Plain username/password values are never written to the database, never
logged, and never returned by panel APIs. Decryption happens only in memory
at the moment a Send2 API call needs the original credentials.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from services.credential_master_key import load_credential_master_key

logger = logging.getLogger("credential_vault")

COLLECTION = "send2_credentials"
NONCE_BYTES = 12


class CredentialVaultError(RuntimeError):
    """Vault operation failed (missing record, decrypt failure, etc.)."""


def _aad(tenant_id: str, krt_unique_id: str) -> bytes:
    return f"{tenant_id}:{krt_unique_id}".encode("utf-8")


def encrypt_value(plain: str, tenant_id: str, krt_unique_id: str) -> str:
    """AES-256-GCM seal. Returns base64(nonce || ciphertext || tag)."""
    if plain is None:
        raise ValueError("plain value is required")
    key = load_credential_master_key()
    nonce = os.urandom(NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(
        nonce,
        str(plain).encode("utf-8"),
        _aad(str(tenant_id), str(krt_unique_id)),
    )
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(stored: str, tenant_id: str, krt_unique_id: str) -> str:
    """Reverse encrypt_value. Tamper / wrong binding / wrong key raises."""
    if not stored:
        raise CredentialVaultError("empty ciphertext")
    try:
        raw = base64.b64decode(stored, validate=True)
    except Exception as exc:
        raise CredentialVaultError("ciphertext is not valid base64") from exc
    if len(raw) <= NONCE_BYTES:
        raise CredentialVaultError("ciphertext too short")
    nonce, ciphertext = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
    key = load_credential_master_key()
    aesgcm = AESGCM(key)
    try:
        plain = aesgcm.decrypt(
            nonce,
            ciphertext,
            _aad(str(tenant_id), str(krt_unique_id)),
        )
    except Exception as exc:
        raise CredentialVaultError("decryption failed") from exc
    return plain.decode("utf-8")


def _repo():
    from db.mongo import Repository
    return Repository(COLLECTION)


def store_send2_credentials(
    tenant_id: str,
    krt_unique_id: str,
    username: str,
    password: str,
    extra: Optional[dict] = None,
) -> None:
    """Encrypt each field and upsert the permanent vault record."""
    tid = (tenant_id or "").strip()
    kid = (krt_unique_id or "").strip()
    if not tid or not kid:
        raise ValueError("tenant_id and krt_unique_id are required")
    if not username or not password:
        raise ValueError("username and password are required")

    extra_obj = dict(extra or {})
    # Never persist customer id as plaintext outside krt_unique_id column.
    enc_username = encrypt_value(str(username), tid, kid)
    enc_password = encrypt_value(str(password), tid, kid)
    enc_extra = encrypt_value(json.dumps(extra_obj, separators=(",", ":")), tid, kid)
    now = datetime.now(timezone.utc)

    _repo().upsert(
        {"tenant_id": tid, "krt_unique_id": kid},
        {
            "tenant_id": tid,
            "krt_unique_id": kid,
            "enc_username": enc_username,
            "enc_password": enc_password,
            "enc_extra": enc_extra,
            "last_synced_at": now,
            "updated_at": now,
        },
    )
    # Log only identifiers + outcome — never credential material.
    logger.info(
        "SEND2_CREDENTIALS_STORED | tenant=%s | krt=%s | at=%s",
        tid,
        kid,
        now.isoformat(),
    )


def get_send2_credentials(tenant_id: str) -> dict:
    """Load the tenant's vault row and return decrypted values in memory only.

    Returns:
        dict with keys: tenant_id, krt_unique_id, username, password, extra,
        last_synced_at (optional).
    """
    tid = (tenant_id or "").strip()
    if not tid:
        raise CredentialVaultError("tenant_id is required")
    row = _repo().find_one({"tenant_id": tid})
    if not row:
        raise CredentialVaultError(f"no Send2 credentials stored for tenant {tid}")
    kid = str(row.get("krt_unique_id") or "").strip()
    if not kid:
        raise CredentialVaultError(f"vault row for tenant {tid} missing krt_unique_id")
    try:
        username = decrypt_value(row["enc_username"], tid, kid)
        password = decrypt_value(row["enc_password"], tid, kid)
        if row.get("enc_extra"):
            extra_raw = decrypt_value(row["enc_extra"], tid, kid)
            extra = json.loads(extra_raw) if extra_raw else {}
        else:
            extra = {}
    except CredentialVaultError:
        raise
    except Exception as exc:
        raise CredentialVaultError("failed to decrypt Send2 credentials") from exc
    return {
        "tenant_id": tid,
        "krt_unique_id": kid,
        "username": username,
        "password": password,
        "extra": extra if isinstance(extra, dict) else {},
        "last_synced_at": row.get("last_synced_at"),
    }


def vault_status(tenant_id: str) -> dict:
    """Masked panel status — never includes credential values."""
    tid = (tenant_id or "").strip()
    if not tid:
        return {"configured": False, "last_synced_at": None}
    row = _repo().find_one({"tenant_id": tid})
    if not row:
        return {"configured": False, "last_synced_at": None}
    return {
        "configured": bool(row.get("enc_username") and row.get("enc_password")),
        "last_synced_at": row.get("last_synced_at"),
    }


def has_vault_record(tenant_id: str) -> bool:
    tid = (tenant_id or "").strip()
    if not tid:
        return False
    row = _repo().find_one({"tenant_id": tid})
    return bool(row and row.get("enc_username") and row.get("enc_password"))


def resolve_krt_unique_id(tenant_id: str) -> str:
    """Resolve the Send2 customer id for a tenant from admins or an existing vault row."""
    tid = (tenant_id or "").strip()
    if not tid:
        raise CredentialVaultError("tenant_id is required")
    row = _repo().find_one({"tenant_id": tid})
    if row and str(row.get("krt_unique_id") or "").strip():
        return str(row["krt_unique_id"]).strip()
    from db.mongo import Repository
    admins = Repository("admins").find_all({"tenant_id": tid}, limit=100)
    for admin in admins:
        kid = str(admin.get("krt_unique_id") or "").strip()
        if kid:
            return kid
    raise CredentialVaultError(
        f"no krt_unique_id for tenant {tid} — set it on a tenant admin before sync"
    )


def vault_fallback_enabled() -> bool:
    return (os.getenv("SEND2_VAULT_FALLBACK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def resolve_send2_username_password(tenant_id: Optional[str]) -> tuple[str, str]:
    """Credentials for one Send2 API call.

    Order:
      1. encrypted vault for the tenant
      2. ``admins`` row for the tenant (Send2 Base64 username + recoverable password)
      3. any recoverable admin / optional env fallback (``SEND2_VAULT_FALLBACK``)

    Failed decryption stops the call — never sends garbage to Send2.
    """
    tid = (tenant_id or "").strip() or None
    if not tid:
        try:
            from routing.database import get_request_tenant
            tid = (get_request_tenant() or "").strip() or None
        except Exception:
            tid = None

    if tid and has_vault_record(tid):
        try:
            creds = get_send2_credentials(tid)
        except CredentialVaultError as exc:
            logger.error(
                "SEND2_VAULT_DECRYPT_FAILED | tenant=%s | error=%s",
                tid,
                type(exc).__name__,
            )
            raise
        return str(creds["username"]), str(creds["password"])

    try:
        try:
            from services.send2_accounts import (
                credentials_from_admins,
                shared_send2_credentials,
            )
        except ImportError:
            from backend.services.send2_accounts import (
                credentials_from_admins,
                shared_send2_credentials,
            )
        if tid:
            pair = credentials_from_admins(tid)
            if pair:
                return pair
        pair = shared_send2_credentials()
        if pair:
            return pair
    except Exception:
        logger.debug("SEND2_ADMINS_CREDS_SKIPPED | tenant=%s", tid, exc_info=True)

    if vault_fallback_enabled():
        from routing.config import SEND2_USERNAME, SEND2_PASSWORD
        if SEND2_USERNAME and SEND2_PASSWORD:
            logger.warning(
                "SEND2_ENV_FALLBACK_USED | tenant=%s | set admins password for this tenant",
                tid or "-",
            )
            return str(SEND2_USERNAME), str(SEND2_PASSWORD)

    raise CredentialVaultError(
        "Send2 username/password not found in vault or admins table "
        "(store recoverable password on the tenant admin; do not rely on .env)"
    )
