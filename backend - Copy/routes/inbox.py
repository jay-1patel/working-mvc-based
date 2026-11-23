import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from database import (
    assign_conversation as assign_inbox_conversation,
    delete_conversation_data,
    get_inbox_queue,
    list_inbox_agents,
    reset_bot_state,
    set_agent_status as set_inbox_agent_status,
    set_human_handover,
)
from routes.auth import get_current_admin

logger = logging.getLogger("inbox")
router = APIRouter(prefix="/api/inbox")


class AssignRequest(BaseModel):
    wa_id: str
    agent_id: str


class HandoverRequest(BaseModel):
    mode: str  # "bot" or "human"


class AgentStatusRequest(BaseModel):
    agent_id: str
    status: str  # "online", "away", "dnd"


@router.get("/queue")
def get_queue(current_admin: dict = Depends(get_current_admin)):
    return {"queue": get_inbox_queue()}


@router.get("/agents")
def get_agents(current_admin: dict = Depends(get_current_admin)):
    return {"agents": list_inbox_agents()}


@router.put("/agents/status")
def set_agent_status(body: AgentStatusRequest, current_admin: dict = Depends(get_current_admin)):
    set_inbox_agent_status(body.agent_id, body.status)
    return {"status": "ok"}


@router.post("/assign")
def assign_conversation(body: AssignRequest, current_admin: dict = Depends(get_current_admin)):
    tid = (current_admin.get("tenant_id") or "").strip() or "default"
    assign_inbox_conversation(tid, body.wa_id, body.agent_id)
    return {"status": "ok", "wa_id": body.wa_id, "agent_id": body.agent_id}


@router.put("/handover/{wa_id}")
def toggle_handover(wa_id: str, body: HandoverRequest, current_admin: dict = Depends(get_current_admin)):
    mode = body.mode
    if mode not in ("bot", "human"):
        raise HTTPException(status_code=400, detail="mode must be 'bot' or 'human'")
    set_human_handover(wa_id, active=(mode == "human"))
    return {"status": "ok", "wa_id": wa_id, "mode": mode}


RESOLVED_MESSAGE = (
    "Thank you for your patience! Your query has been resolved. "
    "The chatbot is now available if you need anything else. 🙏"
)


@router.post("/resolve/{wa_id}")
def resolve_handoff(wa_id: str, current_admin: dict = Depends(get_current_admin)):
    set_human_handover(wa_id, active=False)
    try:
        from routing.config import SEND2_USERNAME, SEND2_PASSWORD
        if SEND2_USERNAME and SEND2_PASSWORD:
            from routing.whatsapp import send_whatsapp_message
            send_whatsapp_message(wa_id, RESOLVED_MESSAGE)
    except Exception as e:
        logger.warning("Could not send resolve message to %s: %s", wa_id, e)
    logger.info("RESOLVED | %s | handoff cleared by admin", wa_id)
    return {"status": "ok", "wa_id": wa_id, "message": RESOLVED_MESSAGE}


@router.post("/reset-bot-state/{wa_id}")
def reset_bot_state_route(wa_id: str, current_admin: dict = Depends(get_current_admin)):
    reset_bot_state(wa_id)
    return {"status": "ok", "wa_id": wa_id}


@router.delete("/conversation/{wa_id}")
def delete_conversation(wa_id: str, current_admin: dict = Depends(get_current_admin)):
    delete_conversation_data(wa_id)
    return {"status": "ok", "wa_id": wa_id}