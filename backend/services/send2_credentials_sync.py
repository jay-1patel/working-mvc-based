"""Sync Send2 credentials into the platform vault.

The HTTP adapter is intentionally thin — fill in when Send2 documents the
credential API. Until then, callers/tests can inject a fixture response.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from services.credential_vault import (
    CredentialVaultError,
    resolve_krt_unique_id,
    store_send2_credentials,
)

logger = logging.getLogger("send2_credentials_sync")


class Send2CredentialsApiNotConfigured(RuntimeError):
    """Raised when SEND2_CREDENTIALS_API_* env vars are missing."""


def send2_fetch_credentials(krt_unique_id: str) -> dict:
    """Fetch plain credentials from Send2 for one customer id.

    TODO(send2-credentials-api): Fill in when Send2 provides the credential
    API details. Still needed from Send2:
      - exact URL path (beyond SEND2_CREDENTIALS_API_URL)
      - authentication scheme (API key header vs basic vs body fields)
      - request body / query parameters for ``krt_unique_id``
      - response JSON field names for customer id, username, password,
        and any additional fields (mapped into ``extra``)

    Expected normalized return (this function's contract):
      {
        "customer_id": "<krt_unique_id or Send2 customer id>",
        "username": "<plain username>",
        "password": "<plain password>",
        "extra": { ... any other fields ... }
      }
    """
    url = (os.getenv("SEND2_CREDENTIALS_API_URL") or "").strip()
    if not url:
        raise Send2CredentialsApiNotConfigured(
            "SEND2_CREDENTIALS_API_URL is not configured"
        )

    api_key = (os.getenv("SEND2_CREDENTIALS_API_KEY") or "").strip()
    api_secret = (os.getenv("SEND2_CREDENTIALS_API_SECRET") or "").strip()
    timeout = float(os.getenv("SEND2_CREDENTIALS_API_TIMEOUT") or "30")

    headers: dict[str, str] = {"Accept": "application/json"}
    # TODO(send2-credentials-api): replace with the auth scheme Send2 documents.
    if api_key:
        headers["X-API-Key"] = api_key
    if api_secret:
        headers["X-API-Secret"] = api_secret

    # TODO(send2-credentials-api): replace query/body shape when documented.
    params = {"krt_unique_id": krt_unique_id, "customer_id": krt_unique_id}

    try:
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            response = client.get(url, headers=headers, params=params)
    except Exception as exc:
        raise RuntimeError("Send2 credentials API request failed") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Send2 credentials API returned HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError("Send2 credentials API returned non-JSON") from exc

    return _normalize_send2_credential_payload(payload, krt_unique_id)


def _normalize_send2_credential_payload(payload: Any, fallback_id: str) -> dict:
    """Map a Send2 response into {customer_id, username, password, extra}."""
    if not isinstance(payload, dict):
        raise RuntimeError("Send2 credentials API response must be a JSON object")

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    customer_id = (
        data.get("customer_id")
        or data.get("krt_unique_id")
        or data.get("customerId")
        or fallback_id
    )
    username = data.get("username") or data.get("user_name") or data.get("userName")
    password = data.get("password")
    if not username or not password:
        raise RuntimeError("Send2 credentials API response missing username/password")

    known = {
        "customer_id",
        "krt_unique_id",
        "customerId",
        "username",
        "user_name",
        "userName",
        "password",
        "data",
    }
    extra = {k: v for k, v in data.items() if k not in known}
    return {
        "customer_id": str(customer_id),
        "username": str(username),
        "password": str(password),
        "extra": extra,
    }


def sync_send2_credentials(
    tenant_id: str,
    *,
    fetch_fn=None,
    krt_unique_id: Optional[str] = None,
) -> dict:
    """Pull plain credentials from Send2, encrypt, and upsert the vault record.

    Logging rule: tenant id + timestamp + success/failure only — never
    credential values in whole or in part.
    """
    tid = (tenant_id or "").strip()
    if not tid:
        raise ValueError("tenant_id is required")
    started = datetime.now(timezone.utc)
    try:
        kid = (krt_unique_id or "").strip() or resolve_krt_unique_id(tid)
        fetcher = fetch_fn or send2_fetch_credentials
        plain = fetcher(kid)
        store_send2_credentials(
            tenant_id=tid,
            krt_unique_id=str(plain.get("customer_id") or kid),
            username=plain["username"],
            password=plain["password"],
            extra=plain.get("extra") or {},
        )
        logger.info(
            "SEND2_CREDENTIALS_SYNC_OK | tenant=%s | at=%s",
            tid,
            started.isoformat(),
        )
        return {
            "ok": True,
            "tenant_id": tid,
            "last_synced_at": started.isoformat(),
        }
    except Exception as exc:
        logger.error(
            "SEND2_CREDENTIALS_SYNC_FAILED | tenant=%s | at=%s | error=%s",
            tid,
            started.isoformat(),
            type(exc).__name__,
        )
        if isinstance(exc, (CredentialVaultError, Send2CredentialsApiNotConfigured, ValueError)):
            raise
        raise RuntimeError("Send2 credentials sync failed") from exc
