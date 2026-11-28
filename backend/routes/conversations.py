"""Tenant-scoped conversations: chat history, live inbox and complaints.

The legacy routes under ``/api/admin`` and ``/api/complaints`` are single-tenant
and global. This router is the tenant-owned path the console uses, so a tenant
console sees only its own customers:

    POST   /api/admin/tenants/conversations              -> flat session list (Chats)
    GET    /api/admin/tenants/{tenant_id}/conversations   -> legacy path list
    POST   /api/admin/tenants/{tenant_id}/conversations/{wa_id}
    GET    /api/admin/tenants/{tenant_id}/chat-history
    GET    /api/admin/tenants/{tenant_id}/inbox
    PUT    /api/admin/tenants/{tenant_id}/inbox/handover/{wa_id}
    POST   /api/admin/tenants/{tenant_id}/inbox/assign
    POST   /api/admin/tenants/{tenant_id}/inbox/resolve/{wa_id}
    GET    /api/admin/tenants/{tenant_id}/agents
    GET    /api/admin/tenants/{tenant_id}/complaints
    PUT    /api/admin/tenants/{tenant_id}/complaints/{ticket_id}
    POST   /api/admin/tenants/{tenant_id}/complaints/{ticket_id}/reply

`chat_history` is stamped with `tenant_id` by the live webhook, which resolves
the owner from the inbound WABA phone-id (`shared.tenancy.resolver`). Rows
written before that column existed fall back to the tenant on their state row
(`user_states.tenant_id`). Complaints carry tenant_id directly.
"""

import asyncio
import json
import logging
import queue as queue_module
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import assign_conversation as assign_inbox_conversation, set_human_handover
from db.conversations_ops import (
    complaint_wa_id,
    conversation_detail,
    customer_360_view,
    delete_tenant_complaint,
    list_tenant_agents,
    list_tenant_complaints,
    list_tenant_conversations,
    patch_complaint_status,
    tenant_chat_history,
    tenant_inbox_queue,
    tenant_owns_conversation,
    update_tenant_complaint,
)
from routes.auth import (
    authorize_tenant_access,
    get_current_admin,
    has_permission,
    require_tenant_access,
    security,
    session_tenant_id,
)
from services.inbox_events import inbox_events

logger = logging.getLogger("conversations")
router = APIRouter(prefix="/api/admin/tenants/{tenant_id}", tags=["conversations"])
flat_router = APIRouter(prefix="/api/admin/tenants", tags=["conversations"])

ALLOWED_STATUSES = {"open", "in_progress", "awaiting_info", "resolved", "closed"}
ALLOWED_PRIORITIES = {"low", "normal", "high", "urgent"}


class ConversationDetailRequest(BaseModel):
    wa_id: str
    limit: int = 300


class ConversationsListRequest(BaseModel):
    """Body for flat POST /conversations (tenant from session)."""
    search: Optional[str] = None
    limit: int = 100


class ConversationThreadRequest(BaseModel):
    """Body for tenant-scoped thread POST (wa_id is in the path)."""
    limit: int = 300


class ChatHistoryRequest(BaseModel):
    days: int = 30
    search: Optional[str] = None
    wa_id: Optional[str] = None
    limit: int = 500


class InboxListRequest(BaseModel):
    include_resolved: bool = True


class InboxHandoverRequest(BaseModel):
    wa_id: str
    mode: str


class InboxAssignRequest(BaseModel):
    wa_id: str
    agent_id: str


class InboxResolveRequest(BaseModel):
    wa_id: str
    reply: bool = True


class InboxReplyRequest(BaseModel):
    wa_id: str
    message: str = ""
    attachment: Optional[dict] = None


class InboxMenuRequest(BaseModel):
    wa_id: str


class InboxAttachmentRequest(BaseModel):
    filename: str
    content: str
    media_type: Optional[str] = None


class AgentsListRequest(BaseModel):
    pass


class ComplaintsListRequest(BaseModel):
    status: Optional[str] = None
    limit: int = 200


class ComplaintUpdateRequest(BaseModel):
    ticket_id: str
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None


class ComplaintReplyRequest(BaseModel):
    ticket_id: str
    message: str
    status: Optional[str] = None


class ComplaintDeleteRequest(BaseModel):
    ticket_id: str


# ── auth ──────────────────────────────────────────────────────────────────

def _require(perm: str):
    def dependency(
        request: Request,
        tenant_id: str,
        principal: dict = Depends(require_tenant_access()),
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> dict:
        if principal.get("type") == "tenant":
            return principal
        if not has_permission(get_current_admin(request, credentials), perm):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action",
            )
        return principal
    return dependency


def _flat_principal(request: Request, credentials, perm: str) -> tuple[dict, str]:
    """Authorize using the tenant bound to username/session_id (not the body)."""
    tenant_id = session_tenant_id(request=request)
    principal = authorize_tenant_access(request, tenant_id, credentials)
    if principal.get("type") == "tenant":
        return principal, tenant_id
    admin = get_current_admin(request, credentials)
    if not has_permission(admin, perm):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
    return principal, tenant_id


def _tenant_scope(alias: str) -> str:
    """Tenant-scope predicate for a chat_history table aliased `alias`.

    A row belongs to the tenant when it is stamped with the tenant id, or -
    for rows written before `chat_history` carried a tenant - when its
    state row does. Two placeholders: the tenant id, twice.
    """
    return (
        f"({alias}.tenant_id = ? OR ({alias}.tenant_id IS NULL AND {alias}.wa_id IN "
        "(SELECT wa_id FROM user_states WHERE tenant_id = ?)))"
    )


#: Tenant scope for the main chat_history queries (alias `ch`).
_TENANT_SCOPE = _tenant_scope("ch")


# ── conversation threads ──────────────────────────────────────────────────

def _format_thread_messages(rows: list) -> list:
    messages = []
    for item in rows:
        raw = item.get("message") or ""
        item["user_message"] = (
            raw.split("] ", 1)[1] if raw.startswith("[") and "] " in raw else raw
        )
        messages.append(item)
    return messages


def _conversation_thread_payload(tenant_id: str, wa_id: str, limit: int) -> dict:
    if limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be less than or equal to 1000")
    detail = conversation_detail(tenant_id, wa_id, limit=limit)
    if not detail.get("owned"):
        raise HTTPException(status_code=404, detail="This conversation does not belong to this tenant")
    return {"wa_id": wa_id, "messages": _format_thread_messages(detail["messages"])}


def _conversations_list_payload(tenant_id: str, limit: int, search: Optional[str]) -> dict:
    """One row per customer: who they are, the last line, and the counts."""
    if limit > 500:
        raise HTTPException(status_code=422, detail="limit must be less than or equal to 500")
    raw = list_tenant_conversations(tenant_id=tenant_id, limit=limit, search=search)
    conversations = [
        {
            "wa_id": t["wa_id"],
            "name": t.get("sender_name") or t["wa_id"],
            "last_message": t.get("last_message") or "",
            "last_at": t.get("last_message_at"),
            "turns": t.get("turns", 0),
            "inbound": t.get("inbound", 0),
            "handover": t.get("handover_mode") == "human",
            "bot_state": t.get("bot_state"),
        }
        for t in raw
    ]
    return {"conversations": conversations, "count": len(conversations)}


@router.get("/conversations")
def list_conversations(
    tenant_id: str,
    limit: int = Query(100, le=500),
    search: Optional[str] = Query(None),
    principal: dict = Depends(_require("chat_history")),
):
    """Legacy path-tenant list; prefer POST /api/admin/tenants/conversations."""
    return _conversations_list_payload(tenant_id, limit, search)


@flat_router.post("/conversations")
def list_conversations_flat(
    body: ConversationsListRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Session-tenant conversation list for the Chats panel (POST)."""
    try:
        _principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    except HTTPException as inbox_exc:
        if inbox_exc.status_code != 403:
            raise
        _principal, tenant_id = _flat_principal(request, credentials, "chat_history")
    return _conversations_list_payload(tenant_id, body.limit, body.search)


@router.post("/conversations/{wa_id}")
def get_conversation_for_tenant(
    tenant_id: str,
    wa_id: str,
    body: Optional[ConversationThreadRequest] = None,
    principal: dict = Depends(_require("view_inbox")),
):
    """Thread for the Chats panel — scoped by path tenant_id (POST)."""
    limit = body.limit if body is not None else 300
    return _conversation_thread_payload(tenant_id, wa_id, limit)


@flat_router.post("/chat/thread")
@flat_router.post("/conversations/detail")  # alias; prefer /chat/thread (no path-route collision)
def get_conversation(
    body: ConversationDetailRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    wa_id, limit = body.wa_id, body.limit
    # Chats uses view_inbox; Past chats uses chat_history. Accept either so the
    # live thread does not 403 into an empty "No messages" state.
    try:
        principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    except HTTPException as inbox_exc:
        if inbox_exc.status_code != 403:
            raise
        principal, tenant_id = _flat_principal(request, credentials, "chat_history")
    return _conversation_thread_payload(tenant_id, wa_id, limit)


@flat_router.post("/chat-history")
def chat_history(
    body: ChatHistoryRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    days, search, wa_id, limit = body.days, body.search, body.wa_id, body.limit
    principal, tenant_id = _flat_principal(request, credentials, "chat_history")
    return tenant_chat_history(
        tenant_id=tenant_id,
        days=days,
        search=search,
        wa_id=wa_id,
        limit=limit,
    )


# ── live inbox (human handover) ───────────────────────────────────────────

@flat_router.post("/inbox")
def inbox_queue(
    body: InboxListRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    include_resolved = body.include_resolved
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    payload = tenant_inbox_queue(tenant_id, include_resolved=include_resolved)
    queue = [
        {
            "wa_id": c["wa_id"],
            "name": c.get("name") or c["wa_id"],
            "last_message": c.get("last_message") or "",
            "last_message_at": c.get("last_message_at"),
            "turns": c.get("unread_count") or c.get("turns") or 0,
            "bot_state": c.get("bot_state"),
            "handover_mode": c.get("handover_mode") or "bot",
            "assigned_agent_id": c.get("assigned_agent_id"),
            "resolved": bool(c.get("resolved")),
        }
        for c in payload.get("conversations", [])
    ]
    queue.sort(key=lambda q: (q["handover_mode"] != "human", str(q.get("last_message_at") or "")))
    handoff = sum(1 for c in queue if c["handover_mode"] == "human")
    return {"queue": queue, "count": len(queue), "handoff_count": handoff}


@flat_router.get("/inbox/events")
async def inbox_events_stream(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Stream tenant-scoped inbox changes for the admin Chats panel."""
    _principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    subscriber = inbox_events.subscribe(tenant_id)

    async def events():
        # The in-process hub is the fast path.  The database fingerprint is
        # the cross-worker path, so an SSE connection still notices changes
        # made by another worker even when no shared pub/sub service exists.
        last_fingerprint = None

        def inbox_fingerprint():
            snapshot = tenant_inbox_queue(tenant_id, include_resolved=True)
            return json.dumps(snapshot.get("conversations", []), sort_keys=True, default=str)

        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 1)
                    last_fingerprint = await asyncio.to_thread(inbox_fingerprint)
                    yield f"event: inbox.updated\ndata: {json.dumps(event)}\n\n"
                except queue_module.Empty:
                    fingerprint = await asyncio.to_thread(inbox_fingerprint)
                    if last_fingerprint is None:
                        last_fingerprint = fingerprint
                    elif fingerprint != last_fingerprint:
                        last_fingerprint = fingerprint
                        yield "event: inbox.updated\ndata: {\"wa_id\": null, \"reason\": \"cross_worker\"}\n\n"
                    else:
                        yield ": heartbeat\n\n"
        finally:
            inbox_events.unsubscribe(tenant_id, subscriber)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class HandoverBody(BaseModel):
    mode: str  # "bot" | "human"


class AssignBody(BaseModel):
    wa_id: str
    agent_id: str


@flat_router.post("/inbox/handover")
def set_handover(
    body: InboxHandoverRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    wa_id = body.wa_id
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    if body.mode not in ("bot", "human"):
        raise HTTPException(status_code=400, detail="mode must be 'bot' or 'human'")
    set_human_handover(wa_id, active=(body.mode == "human"))
    from services.inbox_events import publish_inbox_event
    publish_inbox_event(tenant_id, wa_id, "handover")
    logger.info(f"INBOX_HANDOVER | tenant={tenant_id} | wa={wa_id} | mode={body.mode}")
    return {"status": "ok", "wa_id": wa_id, "mode": body.mode}


@flat_router.post("/inbox/assign")
def assign_conversation(
    body: InboxAssignRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    assign_inbox_conversation(tenant_id, body.wa_id, body.agent_id)
    from services.inbox_events import publish_inbox_event
    publish_inbox_event(tenant_id, body.wa_id, "assign")
    return {"status": "ok", "wa_id": body.wa_id, "agent_id": body.agent_id}


RESOLVED_MESSAGE = (
    "Thank you for your patience! Your query has been resolved. "
    "The chatbot is now available if you need anything else. 🙏"
)


@flat_router.post("/inbox/resolve")
def resolve_handoff(
    body: InboxResolveRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    wa_id, reply = body.wa_id, body.reply
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    set_human_handover(wa_id, active=False)
    from services.inbox_events import publish_inbox_event
    publish_inbox_event(tenant_id, wa_id, "resolve")
    sent = False
    if reply:
        try:
            from routing.whatsapp import send_whatsapp_message
            sent = bool(send_whatsapp_message(wa_id, RESOLVED_MESSAGE, tenant_id=tenant_id))
            if sent:
                try:
                    from services.send_log import log_whatsapp_send, REASON_INBOX
                    log_whatsapp_send(
                        wa_id=wa_id,
                        tenant_id=tenant_id,
                        reason=REASON_INBOX,
                        snippet=RESOLVED_MESSAGE[:120],
                    )
                except Exception:
                    logger.exception("SEND_LOG_RECORD_FAILED | wa=%s tenant=%s reason=inbox_resolved", wa_id, tenant_id)
        except Exception as exc:  # pragma: no cover - depends on live credentials
            logger.warning(f"Could not send resolve message to {wa_id}: {exc}")
    logger.info(f"INBOX_RESOLVED | tenant={tenant_id} | wa={wa_id} | notified={sent}")
    return {"status": "ok", "wa_id": wa_id, "notified": sent, "message": RESOLVED_MESSAGE}


class InboxReply(BaseModel):
    message: str = ""
    attachment: Optional[dict] = None


@flat_router.post("/inbox/reply")
def reply_to_customer(
    body: InboxReplyRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Send an agent's message to the customer and keep the bot out of the way."""
    wa_id = body.wa_id
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    message = (body.message or "").strip()
    attach = body.attachment or None
    attach_url = (attach or {}).get("url") or ""
    attach_type = ((attach or {}).get("type") or "").lower().strip()
    attach_media_type = ((attach or {}).get("media_type") or "").lower().strip()
    attach_name = (attach or {}).get("name") or "attachment"

    # Prefer native WhatsApp image/document when the attachment has a public URL.
    send_as_media = bool(attach_url) and (
        attach_type in ("image", "document")
        or attach_media_type.startswith("image/")
        or attach_media_type in ("application/pdf", "application/octet-stream")
        or attach_url.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"))
    )
    if attach_url and not send_as_media:
        line = f"\U0001F4CE {attach_name}: {attach_url}"
        message = f"{message}\n{line}" if message else line
    if not message and not send_as_media:
        raise HTTPException(status_code=400, detail="message or attachment is required")

    if not tenant_owns_conversation(tenant_id, wa_id):
        raise HTTPException(status_code=404, detail="This conversation does not belong to this tenant")

    try:
        from routing.whatsapp import send_whatsapp_message
        sent = True
        if message:
            sent = bool(send_whatsapp_message(wa_id, message, tenant_id=tenant_id)) and sent
        if send_as_media:
            is_image = (
                attach_type == "image"
                or attach_media_type.startswith("image/")
                or attach_url.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))
            )
            msg_type = "image" if is_image else "document"
            try:
                from kb.services.whatsapp import resolve_public_media_url
                resolved = resolve_public_media_url(attach_url) or attach_url
            except Exception:
                resolved = attach_url
            media_ok = bool(
                send_whatsapp_message(wa_id, resolved, msg_type=msg_type, tenant_id=tenant_id)
            )
            sent = sent and media_ok
            if not media_ok and not message:
                # Last resort: share the URL as text so the customer still gets something.
                fallback = f"\U0001F4CE {attach_name}: {resolved}"
                sent = bool(send_whatsapp_message(wa_id, fallback, tenant_id=tenant_id))
    except Exception as exc:
        logger.error(f"inbox reply send failed: {exc}")
        sent = False
    if not sent:
        raise HTTPException(status_code=502, detail="WhatsApp message could not be sent")

    try:
        from services.send_log import log_whatsapp_send, REASON_INBOX
        log_whatsapp_send(
            wa_id=wa_id,
            tenant_id=tenant_id,
            reason=REASON_INBOX,
            snippet=(message or attach_name or "inbox_reply")[:120],
        )
    except Exception:
        logger.exception("SEND_LOG_RECORD_FAILED | wa=%s tenant=%s reason=inbox_reply", wa_id, tenant_id)

    history_text = message
    if send_as_media:
        history_text = f"{message}\n[attachment:{attach_name}]".strip() if message else f"[attachment:{attach_name}]"
    try:
        from database import save_chat
        save_chat(
            wa_id,
            principal.get("username", "agent"),
            history_text,
            response="[sent by agent]",
            route="agent",
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(f"inbox reply: could not save chat history: {exc}")

    set_human_handover(wa_id, active=True)
    from services.inbox_events import publish_inbox_event
    publish_inbox_event(tenant_id, wa_id, "reply")
    logger.info(f"INBOX_REPLIED | tenant={tenant_id} | wa={wa_id} | by={principal.get('username')}")
    return {"status": "ok", "wa_id": wa_id, "sent": sent}


@flat_router.post("/inbox/menu")
def send_menu_to_customer(
    body: InboxMenuRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Send the tenant's published interactive menu during human handover."""
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    if not tenant_owns_conversation(tenant_id, body.wa_id):
        raise HTTPException(status_code=404, detail="This conversation does not belong to this tenant")

    from shared.tenancy.loader import get_tenant_profile
    profile = get_tenant_profile(tenant_id)
    buttons = profile.menu.visible_buttons(profile.features)
    sections = [{"title": "Options", "rows": [
        {"id": b.id, "title": b.title, "description": getattr(b, "description", "") or ""}
        for b in buttons
    ]}]
    if not buttons:
        raise HTTPException(status_code=400, detail="This tenant has no enabled menu options")

    try:
        from routing.whatsapp import send_whatsapp_list_menu
        sent = bool(send_whatsapp_list_menu(
            body.wa_id, profile.menu.header, profile.menu.body,
            profile.menu.button_text, sections, profile.menu.footer, tenant_id=tenant_id,
        ))
    except Exception as exc:
        logger.error("inbox menu send failed: %s", exc)
        sent = False
    if not sent:
        raise HTTPException(status_code=502, detail="WhatsApp menu could not be sent")

    from database import save_chat
    save_chat(body.wa_id, principal.get("username", "agent"), "[interactive menu]",
              response=profile.menu.body, route="agent", tenant_id=tenant_id)
    set_human_handover(body.wa_id, active=True)
    from services.inbox_events import publish_inbox_event
    publish_inbox_event(tenant_id, body.wa_id, "reply")
    return {"status": "ok", "wa_id": body.wa_id, "sent": True}


@flat_router.post("/inbox/attach")
async def attach_inbox_file(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Host a file on the public application domain for WhatsApp delivery.

    Accepts multipart ``file`` (preferred) or JSON ``{filename, content}`` base64.
    """
    from routes.admin import read_attachment_upload, store_chat_attachment

    _principal, _tenant_id = _flat_principal(request, credentials, "view_inbox")
    filename, content, media_type = await read_attachment_upload(request)
    return await store_chat_attachment(filename, content, media_type)


@flat_router.post("/agents")
def list_agents(
    body: AgentsListRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    principal, tenant_id = _flat_principal(request, credentials, "view_inbox")
    return list_tenant_agents()


# ── complaints ────────────────────────────────────────────────────────────

@flat_router.post("/complaints")
def list_complaints(
    body: ComplaintsListRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    status, limit = body.status, body.limit
    principal, tenant_id = _flat_principal(request, credentials, "view_complaints")
    return list_tenant_complaints(tenant_id, status, limit)


class ComplaintPatch(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None


@flat_router.post("/complaints/update")
def update_complaint(
    body: ComplaintUpdateRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    ticket_id = body.ticket_id
    principal, tenant_id = _flat_principal(request, credentials, "manage_complaints")
    if not any([body.status, body.priority, body.assigned_to is not None]):
        raise HTTPException(status_code=400, detail="Nothing to update")
    if body.status and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if body.priority and body.priority not in ALLOWED_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority must be one of {sorted(ALLOWED_PRIORITIES)}")

    try:
        update_tenant_complaint(
            tenant_id,
            ticket_id,
            status=body.status,
            priority=body.priority,
            assigned_to=body.assigned_to,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Complaint not found for this tenant")
    return {"status": "ok", "ticket_id": ticket_id}


class ComplaintReply(BaseModel):
    message: str
    status: Optional[str] = None


@flat_router.post("/complaints/reply")
def reply_complaint(
    body: ComplaintReplyRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    ticket_id = body.ticket_id
    principal, tenant_id = _flat_principal(request, credentials, "manage_complaints")
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if body.status and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")

    wa_id = complaint_wa_id(tenant_id, ticket_id)
    if not wa_id:
        raise HTTPException(status_code=404, detail="Complaint not found for this tenant")
    if not wa_id:
        raise HTTPException(status_code=400, detail="Complaint has no customer to reply to")

    try:
        from routing.whatsapp import send_whatsapp_message
        sent = bool(send_whatsapp_message(wa_id, message, tenant_id=tenant_id))
    except Exception as exc:
        logger.error(f"reply_complaint send failed: {exc}")
        sent = False
    if not sent:
        raise HTTPException(status_code=502, detail="WhatsApp message could not be sent")

    try:
        from database import save_chat
        save_chat(wa_id, principal.get("username", "agent"), message,
                  response="[sent via complaint]", route="complaint", tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(f"reply_complaint: could not save chat history: {exc}")

    if body.status:
        patch_complaint_status(tenant_id, ticket_id, body.status)

    if body.status in ("awaiting_info", "in_progress"):
        set_human_handover(wa_id, True)
    elif body.status in ("resolved", "closed"):
        set_human_handover(wa_id, False)

    logger.info(f"COMPLAINT_REPLIED | tenant={tenant_id} | {ticket_id} | to={wa_id} | status={body.status or 'unchanged'}")
    return {"status": "ok", "ticket_id": ticket_id, "wa_id": wa_id, "sent": sent, "new_status": body.status}


@flat_router.post("/complaints/delete")
def delete_complaint(
    body: ComplaintDeleteRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    ticket_id = body.ticket_id
    principal, tenant_id = _flat_principal(request, credentials, "manage_complaints")
    try:
        delete_tenant_complaint(tenant_id, ticket_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Complaint not found for this tenant")
    return {"status": "ok", "ticket_id": ticket_id}


@router.get("/customer-360/{wa_id}")
def customer_360(
    tenant_id: str,
    wa_id: str,
    limit: int = Query(50, ge=1, le=200),
    principal: dict = Depends(_require("view_inbox")),
):
    """One-number story: profile, session/state, chat, orders, CRM, send log.

    ``wa_id`` may be digits with or without ``+`` / spaces; we normalize to digits
    and also match ``customers.phone`` when it differs from the WhatsApp id.
    """
    from db.conversations_ops import _normalize_lookup_phone

    digits = _normalize_lookup_phone(wa_id)
    if not digits:
        raise HTTPException(status_code=400, detail="wa_id / mobile number required")
    return customer_360_view(tenant_id, digits, limit)
