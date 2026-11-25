import logging
import os
import json
import mimetypes

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from database import list_chat_thread, save_chat, touch_handover_activity
from routes.auth import get_current_admin, scoped_tenant_id
from routing.config import (
    SEND2_NUMBER,
    SEND2_SESSION_SEND_URL,
    SEND_MEDIA,
)


def _send2_login(tenant_id: str = None):
    try:
        from services.credential_vault import resolve_send2_username_password
    except ImportError:
        from backend.services.credential_vault import resolve_send2_username_password
    return resolve_send2_username_password(tenant_id)

logger = logging.getLogger("chat")
router = APIRouter(prefix="/api/chat")

class SendMessageRequest(BaseModel):
    wa_id: str
    message: str
    sender_type: str = "agent"
    sender: str = "admin"


# ── Chat history for a WhatsApp user ──────────────────────────────────────

@router.get("/history/{wa_id}")
def get_chat_history_for_user(wa_id: str, current_admin: dict = Depends(get_current_admin)):
    # A tenant admin only sees this WhatsApp id's thread inside their own tenant.
    # The same phone can talk to several brands; wa_id alone is not a scope.
    scope = scoped_tenant_id(current_admin)
    rows = list_chat_thread(wa_id, tenant_id=scope, limit=200)

    messages = []
    for row in rows:
        if row["message"]:
            messages.append({
                "id": row["id"],
                "role": "user",
                "sender": row["sender_name"] or row["wa_id"],
                "text": row["message"],
                "created_at": row["created_at"],
            })
        if row["response"]:
            messages.append({
                "id": row["id"],
                "role": "bot",
                "sender": "bot",
                "text": row["response"],
                "created_at": row["created_at"],
            })

    return {"messages": messages}


# ── Upload helpers ─────────────────────────────────────────────────────────

def _upload_to_catbox(content: bytes, filename: str) -> str | None:
    """Legacy helper name: store the document on this backend."""
    try:
        from services.media_host import upload_public_media
    except ImportError:
        from backend.services.media_host import upload_public_media
    try:
        return upload_public_media(content, filename, subdir="brochures")
    except Exception as e:
        logger.error(f"Local document hosting failed: {e}")
    return None


# The implementation lives in the services layer (services/image_upload.py)
# so services no longer import from this route module. Re-exported here so
# existing `from routes.chat import _upload_to_imghippo` callers keep working.
try:
    from services.image_upload import _upload_to_imghippo
except ImportError:
    from backend.services.image_upload import _upload_to_imghippo


def _guess_media_type(filename: str, content_type: str = "") -> str:
    """Determine WhatsApp media_type from filename/content-type."""
    ct = content_type.lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        return "image"
    if ext in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        return "video"
    return "document"


# ── Send via send2.digital ────────────────────────────────────────────────

def _send_text_via_send2(wa_id: str, text: str, tenant_id: str = None) -> dict:
    """Send text message via send2.digital."""
    url = SEND2_SESSION_SEND_URL
    username, password = _send2_login(tenant_id)
    payload = {
        "user_name": username,
        "password": password,
        "contact_no": wa_id,
        "message_type": "text",
        "message": text,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"send2 text error: {e}")
        return {"error": str(e)}


def _send_media_via_send2(wa_id: str, media_type: str, media_url: str, caption: str = None, tenant_id: str = None) -> dict:
    """Send media message via send2.digital."""
    url = SEND2_SESSION_SEND_URL
    username, password = _send2_login(tenant_id)
    payload = {
        "user_name": username,
        "password": password,
        "contact_no": wa_id,
        "message_type": media_type,
        "message": media_url,
    }
    if caption:
        payload["caption"] = caption
    try:
        resp = httpx.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"send2 media error: {e}")
        return {"error": str(e)}


# ── Send message from agent to user ───────────────────────────────────────

@router.post("/send")
async def send_message(
    request: Request,
    current_admin: dict = Depends(get_current_admin),
):
    content_type = request.headers.get("content-type", "")

    wa_id = None
    message = ""
    sender = current_admin.get("username", "agent")
    uploaded_file = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        wa_id = form.get("wa_id")
        message = form.get("caption", "") or ""
        uploaded_file = form.get("file")
    else:
        body = await request.json()
        wa_id = body.get("wa_id")
        message = body.get("message", "")
        sender = body.get("sender", sender)

    if not wa_id:
        raise HTTPException(status_code=400, detail="wa_id is required")

    tenant_id = scoped_tenant_id(current_admin)
    result = {}

    if uploaded_file and hasattr(uploaded_file, "read"):
        # Read file content
        file_content = await uploaded_file.read()
        filename = uploaded_file.filename or "file"
        file_ct = getattr(uploaded_file, "content_type", "") or ""

        # Store on this backend so the configured client can fetch the file.
        media_type = _guess_media_type(filename, file_ct)
        subdir = "chat_attachments" if media_type != "image" else "product_images"
        try:
            from services.media_host import upload_public_media
        except ImportError:
            from backend.services.media_host import upload_public_media
        media_url = upload_public_media(
            file_content, filename, file_ct, subdir=subdir
        )
        if not media_url:
            raise HTTPException(
                status_code=500,
                detail=(
                    "File upload failed. Set PUBLIC_BASE_URL and verify UPLOAD_DIR."
                ),
            )

        # Send media via send2.digital
        result = _send_media_via_send2(
            wa_id, media_type, media_url, caption=message or None, tenant_id=tenant_id
        )

        # Save to chat_history
        save_chat(wa_id, sender, message or f"[{media_type}] {filename}", response=None, route="agent")
    else:
        # Text-only message
        result = _send_text_via_send2(wa_id, message, tenant_id=tenant_id)
        save_chat(wa_id, sender, message, response=None, route="agent")

    # A human agent has just responded: keep the handoff alive by resetting the
    # auto-revert timer. If this conversation is not in human_handover mode the
    # row is simply left untouched (no-op update).
    _touch_handover_activity(wa_id)

    return {"status": "ok", "wa_id": wa_id, "result": result}


def _touch_handover_activity(wa_id: str) -> None:
    """Refresh user_states.updated_at so the 1h auto-revert timeout is measured
    from the last human-agent reply rather than from the handoff start."""
    touch_handover_activity(wa_id)
