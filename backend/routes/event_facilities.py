"""Admin CRUD for event facility location pins — POST-only endpoints."""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from routes.auth import get_current_admin, require_tenant_access
from db import event_facilities as fac_db

logger = logging.getLogger("routes.event_facilities")

router = APIRouter(prefix="/api/admin/tenants/{tenant_id}", tags=["event-facilities"])

FACILITY_TYPES = frozenset({
    "medical", "police", "ambulance", "women", "reunion", "lost_counter",
})
EVENTS = frozenset({"gangasagar", "kumbh", "rath_yatra"})


class FacilityListIn(BaseModel):
    event: Optional[str] = None
    type: Optional[str] = None
    active_only: bool = False


class FacilityIn(BaseModel):
    event: str
    type: str
    name: str
    address: str = ""
    latitude: float
    longitude: float
    message: str = ""
    is_active: int = 1
    sort_order: int = 0

    @field_validator("event")
    @classmethod
    def _event_ok(cls, v: str) -> str:
        val = str(v or "").strip().lower()
        if val not in EVENTS:
            raise ValueError(f"event must be one of {sorted(EVENTS)}")
        return val

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        val = str(v or "").strip().lower()
        if val not in FACILITY_TYPES:
            raise ValueError(f"type must be one of {sorted(FACILITY_TYPES)}")
        return val

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        val = str(v or "").strip()
        if not val:
            raise ValueError("name is required")
        return val


class FacilityUpdateIn(BaseModel):
    id: int
    event: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    message: Optional[str] = None
    is_active: Optional[int] = None
    sort_order: Optional[int] = None


class FacilityDeleteIn(BaseModel):
    id: int
    hard: bool = False


def _public(row: dict) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "event": row.get("event"),
        "type": row.get("type"),
        "name": row.get("name"),
        "address": row.get("address") or "",
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "message": row.get("message") or "",
        "is_active": int(row.get("is_active") or 0),
        "sort_order": int(row.get("sort_order") or 0),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.post("/event-facilities/list")
def list_facilities(
    tenant_id: str,
    body: Optional[FacilityListIn] = None,
    current_admin: dict = Depends(get_current_admin),
    _access=Depends(require_tenant_access()),
):
    req = body or FacilityListIn()
    rows = fac_db.list_event_facilities(
        tenant_id,
        event=req.event,
        facility_type=req.type,
        active_only=req.active_only,
    )
    return {"facilities": [_public(r) for r in rows], "count": len(rows)}


@router.post("/event-facilities/create")
def create_facility(
    tenant_id: str,
    body: FacilityIn,
    current_admin: dict = Depends(get_current_admin),
    _access=Depends(require_tenant_access()),
):
    try:
        row = fac_db.create_event_facility({**body.model_dump(), "tenant_id": tenant_id})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "facility": _public(row)}


@router.post("/event-facilities/update")
def update_facility(
    tenant_id: str,
    body: FacilityUpdateIn,
    current_admin: dict = Depends(get_current_admin),
    _access=Depends(require_tenant_access()),
):
    changes = {
        k: v for k, v in body.model_dump().items()
        if k != "id" and v is not None
    }
    if "event" in changes and str(changes["event"]).lower() not in EVENTS:
        raise HTTPException(status_code=400, detail="invalid event")
    if "type" in changes and str(changes["type"]).lower() not in FACILITY_TYPES:
        raise HTTPException(status_code=400, detail="invalid type")
    row = fac_db.update_event_facility(body.id, changes, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="facility not found")
    return {"ok": True, "facility": _public(row)}


@router.post("/event-facilities/delete")
def delete_facility(
    tenant_id: str,
    body: FacilityDeleteIn,
    current_admin: dict = Depends(get_current_admin),
    _access=Depends(require_tenant_access()),
):
    ok = fac_db.delete_event_facility(body.id, tenant_id=tenant_id, hard=body.hard)
    if not ok:
        raise HTTPException(status_code=404, detail="facility not found")
    return {"ok": True, "deleted": body.id, "hard": body.hard}
