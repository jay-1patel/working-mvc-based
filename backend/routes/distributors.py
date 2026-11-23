import json
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import (
    count_distributors as count_tenant_distributors,
    delete_distributor as remove_distributor,
    distributor_exists_globally,
    get_distributor,
    insert_distributor,
    list_distributors as list_tenant_distributors,
    record_admin_audit_event,
    update_distributor as patch_distributor,
)
from db.core import use_mongodb
from routes.auth import require_permission, require_tenant_access
from shared.tenancy.gating import is_enabled
from shared.tenancy.schemas import is_valid_email, is_valid_phone

logger = logging.getLogger("distributors")


def _require_distributors(tenant_id: str):
    import os
    from shared.tenancy import store, CLIENTS_DIR
    client_dir_exists = (CLIENTS_DIR / tenant_id).is_dir() if hasattr(CLIENTS_DIR, "is_dir") else os.path.isdir(os.path.join(CLIENTS_DIR, tenant_id))
    if client_dir_exists or store.get_tenant(tenant_id):
        if not is_enabled(tenant_id, "distributors"):
            raise HTTPException(
                status_code=403,
                detail=f"Distributors feature is not enabled for tenant '{tenant_id}'",
            )


router = APIRouter(
    prefix="/api/admin/tenants/{tenant_id}/distributors",
    tags=["distributors"],
    dependencies=[Depends(_require_distributors)],
)


# ── Pydantic models ────────────────────────────────────────────────────

class DistributorCreate(BaseModel):
    wa_id: str
    name: str = ""
    phone: str = ""
    email: str = ""
    region: str = ""
    city: str = ""
    address: str = ""
    service_area: str = ""
    tier: str = "Bronze"
    product_interests: list[str] = []
    sales_volume: float = 0
    last_order_value: float = 0
    outstanding_payments: float = 0
    notes: str = ""


class DistributorUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    service_area: str | None = None
    tier: str | None = None
    product_interests: list[str] | None = None
    sales_volume: float | None = None
    last_order_value: float | None = None
    outstanding_payments: float | None = None
    notes: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────

def _contact_errors(name=None, phone=None, email=None, wa_id=None):
    """Collect the compulsory / format problems with one submission.

    None means "not part of this submission" (partial updates only validate
    the fields they actually carry).
    """
    errors = []
    if name is not None and not str(name).strip():
        errors.append("name is required")
    if phone is not None:
        if not str(phone).strip():
            errors.append("phone is required")
        elif not is_valid_phone(phone):
            errors.append(
                "phone must be a 10-digit number (or country code followed by 10 digits, e.g. +91 98765 43210)"
            )
    if email is not None:
        if not str(email).strip():
            errors.append("email is required")
        elif not is_valid_email(email):
            errors.append("email must be a valid address, e.g. name@company.com")
    if wa_id is not None and not re.fullmatch(r"\d{15}", wa_id):
        errors.append("the WhatsApp phone number id must be exactly 15 digits")
    return errors


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("")
def list_distributors(
    tenant_id: str,
    q: str = "",
    region: str = "",
    tier: str = "",
    current_admin: dict = Depends(require_tenant_access()),
):
    """List this tenant's distributors, with optional search / filter."""
    return {
        "distributors": list_tenant_distributors(
            tenant_id, q=q, region=region, tier=tier
        )
    }


@router.get("/count")
def distributor_count(
    tenant_id: str,
    region: str = "",
    tier: str = "",
    product_interest: str = "",
    current_admin: dict = Depends(require_tenant_access()),
):
    """Count this tenant's distributors matching optional segment filters.
    Used by Campaign Builder for the live 'target N distributors' preview.
    """
    return {
        "count": count_tenant_distributors(
            tenant_id, region=region, tier=tier, product_interest=product_interest
        )
    }


@router.get("/lookup/{wa_id}")
def lookup_distributor(
    tenant_id: str,
    wa_id: str,
    current_admin: dict = Depends(require_tenant_access()),
):
    """Fetch one of this tenant's distributors by WhatsApp ID."""
    row = get_distributor(tenant_id, wa_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Distributor '{wa_id}' not found")
    return row


@router.post("")
def create_distributor(
    tenant_id: str,
    body: DistributorCreate,
    current_admin: dict = Depends(require_permission("manage_distributors")),
):
    """Add a new distributor to this tenant."""
    wa_id = body.wa_id.strip()

    if not wa_id:
        raise HTTPException(400, "wa_id is required")

    errors = _contact_errors(name=body.name, phone=body.phone, email=body.email, wa_id=wa_id)
    if errors:
        raise HTTPException(422, "; ".join(errors))

    if distributor_exists_globally(wa_id):
        raise HTTPException(409, f"Distributor with wa_id '{wa_id}' already exists")

    insert_distributor(tenant_id, body)
    audit = dict(
        action="distributor_created",
        actor=current_admin,
        resource_type="distributor",
        resource_id=wa_id,
        tenant_id=tenant_id,
        details={
            "wa_id": wa_id,
            "name": str(body.name)[:100],
            "phone": str(body.phone)[:30],
            "region": str(body.region)[:50],
            "tier": str(body.tier)[:30],
        },
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit)

    logger.info(f"DISTRIBUTOR_CREATED | tenant={tenant_id} | wa_id={wa_id} | name={body.name}")
    return {"ok": True, "wa_id": wa_id}


@router.put("/{wa_id}")
def update_distributor(
    tenant_id: str,
    wa_id: str,
    body: DistributorUpdate,
    current_admin: dict = Depends(require_permission("manage_distributors")),
):
    """Update one of this tenant's distributors (partial update — only sent fields)."""
    updates = body.model_dump(exclude_unset=True)

    errors = _contact_errors(
        name=updates.get("name"),
        phone=updates.get("phone"),
        email=updates.get("email"),
    )
    if errors:
        raise HTTPException(422, "; ".join(errors))

    if not updates:
        raise HTTPException(400, "Nothing to update")

    try:
        _, changes = patch_distributor(tenant_id, wa_id, updates)
    except LookupError:
        raise HTTPException(404, f"Distributor '{wa_id}' not found")

    audit = dict(
        action="distributor_updated",
        actor=current_admin,
        resource_type="distributor",
        resource_id=wa_id,
        tenant_id=tenant_id,
        details={
            "wa_id": wa_id,
            "changed_fields": sorted(updates.keys()),
            "changes": changes,
        },
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit)

    logger.info(f"DISTRIBUTOR_UPDATED | tenant={tenant_id} | wa_id={wa_id}")
    return {"ok": True}


@router.delete("/{wa_id}")
def delete_distributor(
    tenant_id: str,
    wa_id: str,
    current_admin: dict = Depends(require_permission("manage_distributors")),
):
    """Delete one of this tenant's distributors."""
    row = remove_distributor(tenant_id, wa_id)
    if not row:
        raise HTTPException(404, f"Distributor '{wa_id}' not found")

    audit = dict(
        action="distributor_deleted",
        actor=current_admin,
        resource_type="distributor",
        resource_id=wa_id,
        tenant_id=tenant_id,
        details={
            "wa_id": wa_id,
            "name": (row.get("name") or "")[:100],
            "phone": (row.get("phone") or "")[:30],
        },
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit)

    logger.info(f"DISTRIBUTOR_DELETED | tenant={tenant_id} | wa_id={wa_id}")
    return {"ok": True}
