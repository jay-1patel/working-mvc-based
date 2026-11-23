"""
Leads inbox (Phase 6) — the CRM hand-off surface for flow-runner leads.
"""
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import (
    LEAD_STATUS_CHOICES,
    export_lead_rows,
    get_lead,
    list_admin_leads,
    update_lead_record,
)
from routes.auth import require_permission

logger = logging.getLogger("leads")

router = APIRouter(prefix="/api/leads", tags=["leads"])

LEAD_STATUSES = LEAD_STATUS_CHOICES


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None


@router.get("")
def list_leads(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_admin: dict = Depends(require_permission("manage_operations")),
):
    if status and status not in LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown status '{status}'")
    return list_admin_leads(
        tenant_id=tenant_id,
        status=status,
        assignee=assignee,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/export.csv")
def export_leads(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    current_admin: dict = Depends(require_permission("manage_operations")),
):
    if status and status not in LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown status '{status}'")
    rows = export_lead_rows(tenant_id=tenant_id, status=status, assignee=assignee)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "tenant_id", "wa_id", "user_name", "phone", "email",
        "collected", "status", "assignee", "source", "flow",
        "created_at", "updated_at",
    ])
    for r in rows:
        writer.writerow([
            r.get("id"), r.get("tenant_id"), r.get("wa_id"), r.get("user_name"),
            r.get("phone"), r.get("email"), r.get("collected"), r.get("status"),
            r.get("assignee"), r.get("source"), r.get("flow"),
            r.get("created_at"), r.get("updated_at"),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/{lead_id}")
def get_lead_route(
    lead_id: int,
    current_admin: dict = Depends(require_permission("manage_operations")),
):
    row = get_lead(lead_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    return row


@router.put("/{lead_id}")
def update_lead(
    lead_id: int,
    body: LeadUpdate,
    current_admin: dict = Depends(require_permission("manage_operations")),
):
    if body.status and body.status not in LEAD_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown status '{body.status}'. Valid: {list(LEAD_STATUSES)}",
        )
    if not body.status and body.assignee is None:
        raise HTTPException(status_code=400, detail="Nothing to update")

    row = update_lead_record(lead_id, status=body.status, assignee=body.assignee)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    return row