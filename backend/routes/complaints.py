"""Admin API for the complaints raised through the WhatsApp bot."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database import (
    delete_complaint as remove_complaint,
    get_complaint,
    list_complaints as list_admin_complaints,
    record_admin_audit_event,
    resolve_complaint as mark_complaint_resolved,
    save_chat,
    set_human_handover,
    update_complaint as patch_complaint,
)
from db.core import use_mongodb
from routes.auth import require_permission

logger = logging.getLogger("complaints")
router = APIRouter(prefix="/api/complaints")

ALLOWED_STATUSES = {"open", "in_progress", "awaiting_info", "resolved", "closed"}


class ComplaintUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None


class ComplaintReply(BaseModel):
    message: str
    status: Optional[str] = None


@router.get("")
def list_complaints(
    status: Optional[str] = Query(None),
    wa_id: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
    current_admin: dict = Depends(require_permission("view_complaints")),
):
    return list_admin_complaints(status=status, wa_id=wa_id, limit=limit)


@router.get("/{ticket_id}")
def get_complaint_route(
    ticket_id: str,
    current_admin: dict = Depends(require_permission("view_complaints")),
):
    row = get_complaint(ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"complaint": row}


@router.put("/{ticket_id}")
def update_complaint(
    ticket_id: str,
    body: ComplaintUpdate,
    current_admin: dict = Depends(require_permission("manage_complaints")),
):
    if not any([body.status, body.assigned_to, body.priority]):
        raise HTTPException(status_code=400, detail="Nothing to update")
    if body.status and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")

    row_id = patch_complaint(
        ticket_id,
        status=body.status,
        assigned_to=body.assigned_to,
        priority=body.priority,
    )
    if row_id is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    changed_fields = []
    if body.status:
        changed_fields.append(f"status:{body.status}")
    if body.assigned_to is not None:
        changed_fields.append(f"assigned_to:{body.assigned_to}")
    if body.priority:
        changed_fields.append(f"priority:{body.priority}")

    audit = dict(
        action="complaint_updated",
        actor=current_admin,
        resource_type="complaint",
        resource_id=row_id,
        details={"ticket_id": ticket_id, "changed_fields": changed_fields},
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit)

    return {"status": "ok", "ticket_id": ticket_id, "updated": {k: v for k, v in body.dict().items() if v is not None}}


@router.post("/{ticket_id}/resolve")
def resolve_complaint(
    ticket_id: str,
    current_admin: dict = Depends(require_permission("manage_complaints")),
):
    from datetime import datetime

    now = datetime.utcnow().isoformat()
    row_id = mark_complaint_resolved(ticket_id)
    if row_id is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    audit = dict(
        action="complaint_resolved",
        actor=current_admin,
        resource_type="complaint",
        resource_id=row_id,
        details={"ticket_id": ticket_id, "resolved_at": now},
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit)
    return {"status": "ok", "ticket_id": ticket_id, "resolved": True}


@router.post("/{ticket_id}/reply")
def reply_complaint(
    ticket_id: str,
    body: ComplaintReply,
    current_admin: dict = Depends(require_permission("manage_complaints")),
):
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if body.status and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")

    row = get_complaint(ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")
    wa_id = row.get("wa_id")
    if not wa_id:
        raise HTTPException(status_code=400, detail="Complaint has no customer WA ID to reply to")

    try:
        from routing.whatsapp import send_whatsapp_message
        sent = send_whatsapp_message(wa_id, message)
    except Exception as e:
        logger.error("reply_complaint send failed: %s", e)
        sent = False
    if not sent:
        raise HTTPException(status_code=502, detail="WhatsApp message could not be sent")

    try:
        save_chat(wa_id, current_admin.get("username", "agent"), message, response="[sent via complaint]", route="complaint")
    except Exception as e:
        logger.warning("reply_complaint: could not save chat history: %s", e)

    if body.status:
        patch_complaint(ticket_id, status=body.status)

    if body.status in ("awaiting_info", "in_progress"):
        set_human_handover(wa_id, True)
        logger.info("COMPLAINT_HANDOVER_ON | %s | %s", ticket_id, wa_id)
    elif body.status in ("resolved", "closed"):
        set_human_handover(wa_id, False)
        logger.info("COMPLAINT_HANDOVER_OFF | %s | %s", ticket_id, wa_id)

    logger.info(
        "COMPLAINT_REPLIED | %s | to=%s | status=%s | by=%s",
        ticket_id, wa_id, body.status or "unchanged", current_admin.get("username"),
    )
    return {"status": "ok", "ticket_id": ticket_id, "wa_id": wa_id, "sent": sent, "new_status": body.status}


@router.delete("/{ticket_id}")
def delete_complaint(
    ticket_id: str,
    current_admin: dict = Depends(require_permission("manage_complaints")),
):
    row = remove_complaint(ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")

    audit = dict(
        action="complaint_deleted",
        actor=current_admin,
        resource_type="complaint",
        resource_id=row.get("id"),
        details={
            "ticket_id": ticket_id,
            "wa_id": row.get("wa_id"),
            "complaint_type": row.get("complaint_type"),
            "description": row.get("description"),
        },
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit)

    logger.info("COMPLAINT_DELETED | %s | by %s", ticket_id, current_admin.get("username"))
    return {"status": "ok", "ticket_id": ticket_id}