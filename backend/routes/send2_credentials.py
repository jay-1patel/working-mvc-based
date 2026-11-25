"""Panel APIs for Send2 credential vault status (masked) and super-admin re-sync."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from routes.auth import (
    get_current_admin,
    require_super_admin,
    security,
    session_tenant_id,
)
from services.credential_vault import vault_status
from services.send2_credentials_sync import (
    Send2CredentialsApiNotConfigured,
    sync_send2_credentials,
)

logger = logging.getLogger("send2_credentials_routes")

flat_router = APIRouter(prefix="/api/admin/tenants", tags=["send2-credentials"])
router = APIRouter(prefix="/api/admin/tenants", tags=["send2-credentials"])


class Send2CredentialsStatusRequest(BaseModel):
    """Empty body — tenant comes from the login session only."""


class Send2CredentialsResyncRequest(BaseModel):
    """Optional override for tests; production resolves krt from the tenant admin."""
    krt_unique_id: Optional[str] = None


@flat_router.post("/send2-credentials/status")
def send2_credentials_status(
    body: Send2CredentialsStatusRequest = None,
    request: Request = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Masked status for the caller's session tenant. Never returns secrets."""
    admin = get_current_admin(request, credentials)
    tenant_id = session_tenant_id(admin=admin, request=request)
    status = vault_status(tenant_id)
    return {
        "configured": bool(status.get("configured")),
        "last_synced_at": status.get("last_synced_at"),
    }


@router.post("/{tenant_id}/send2-credentials/resync")
def send2_credentials_resync(
    tenant_id: str,
    body: Send2CredentialsResyncRequest = None,
    current_admin: dict = Depends(require_super_admin),
):
    """Super-admin only: re-pull credentials from Send2 after a password rotation."""
    tid = (tenant_id or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    kid = (body.krt_unique_id if body else None) or None
    try:
        result = sync_send2_credentials(tid, krt_unique_id=kid)
    except Send2CredentialsApiNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Do not leak credential material or Send2 response bodies.
        logger.error(
            "SEND2_CREDENTIALS_RESYNC_HTTP_FAILED | tenant=%s | by=%s | error=%s",
            tid,
            current_admin.get("username"),
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail="Send2 credentials sync failed") from exc
    logger.info(
        "SEND2_CREDENTIALS_RESYNC_OK | tenant=%s | by=%s",
        tid,
        current_admin.get("username"),
    )
    return {
        "ok": True,
        "tenant_id": tid,
        "last_synced_at": result.get("last_synced_at"),
        "configured": True,
    }
