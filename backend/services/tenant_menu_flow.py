"""Generic DB-backed hierarchical WhatsApp menus for any tenant.

Menu structure is stored in the tenant's published profile as ``menu.buttons``.
Each button may optionally carry a ``parent_id``, making it a child of another
button.  This keeps the existing flat-menu behaviour intact while allowing
arbitrary nesting depth.

Row ids are prefixed with ``tm_`` so they never collide with hard-coded
spiritual or legacy ``menu_*`` ids.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("services.tenant_menu_flow")

_MENU_NODE_PREFIX = "tm_"
_BACK_ID = "tm_back"
_MAIN_ID = "main_menu"


def _norm(text: str) -> str:
    cleaned = re.sub(r"[\W_]+", " ", str(text or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _sender():
    try:
        from services import whatsapp_sender as sender
    except ImportError:
        from backend.services import whatsapp_sender as sender
    return sender


def _load_nodes(tenant_id: str | None) -> list[dict[str, Any]]:
    """Return all menu buttons for the tenant's published profile."""
    if not tenant_id:
        return []
    try:
        from shared.tenancy.loader import get_tenant_profile
        profile = get_tenant_profile(tenant_id)
        menu = getattr(profile, "menu", None)
        buttons = getattr(menu, "buttons", None) or []
        return [b.model_dump() if hasattr(b, "model_dump") else dict(b) for b in buttons]
    except Exception as exc:
        logger.debug("TENANT_MENU_LOAD_FAILED | tenant=%s | %s", tenant_id, exc)
        return []


def _children_of(nodes: list[dict], parent_id: str | None) -> list[dict]:
    result = []
    for n in nodes:
        pid = str(n.get("parent_id") or "").strip() or None
        if pid == parent_id:
            if n.get("enabled", True) is False:
                continue
            result.append(n)
    result.sort(key=lambda x: int(x.get("sort_order") or 0))
    return result


def _node_by_id(nodes: list[dict], node_id: str) -> dict | None:
    for n in nodes:
        if str(n.get("id") or "") == node_id:
            return n
    return None


def _set_current_node(wa_id: str, node_id: str | None, *, tenant_id: str | None) -> None:
    try:
        from database import update_user_context
        update_user_context(wa_id, {"tenant_menu_current": node_id}, tenant_id=tenant_id)
    except Exception:
        logger.debug("TENANT_MENU_NODE_SAVE_SKIPPED", exc_info=True)


def _get_current_node(wa_id: str, *, tenant_id: str | None) -> str | None:
    try:
        from database import get_user_state
        row = get_user_state(wa_id, tenant_id=tenant_id) or {}
        import json
        ctx = row.get("context") if isinstance(row, dict) else None
        if isinstance(ctx, str):
            ctx = json.loads(ctx or "{}")
        val = (ctx or {}).get("tenant_menu_current")
        return str(val).strip() if val else None
    except Exception:
        logger.debug("TENANT_MENU_NODE_LOAD_SKIPPED", exc_info=True)
        return None


async def _send_node_list(
    wa_id: str,
    nodes: list[dict],
    parent_id: str | None,
    *,
    tenant_id: str | None,
) -> bool:
    children = _children_of(nodes, parent_id)
    if not children:
        await _sender().send_text_message(
            wa_id,
            "No options are available right now. Reply *menu* for the main menu.",
            tenant_id=tenant_id,
        )
        return True

    rows = []
    for node in children:
        nid = str(node.get("id") or "").strip()
        if not nid:
            continue
        rows.append({
            "id": f"{_MENU_NODE_PREFIX}{nid}",
            "title": str(node.get("title") or "")[:24],
            "description": str(node.get("description") or "")[:72],
        })
    if parent_id:
        rows.append({"id": _BACK_ID, "title": "Back", "description": "Previous menu"})
    rows.append({"id": _MAIN_ID, "title": "Main Menu", "description": "All options"})

    if len(rows) <= 4:
        buttons = [{"id": r["id"], "title": r["title"]} for r in rows]
        return await _sender().send_button_message(
            wa_id,
            "Choose an option:",
            buttons,
            tenant_id=tenant_id,
        )

    return await _sender().send_list_menu(
        wa_id,
        "Menu",
        "Choose an option:",
        "Options",
        [{"title": "Options", "rows": rows}],
        tenant_id=tenant_id,
    )


async def _answer_node(
    wa_id: str,
    node: dict,
    *,
    tenant_id: str | None,
) -> None:
    action = str(node.get("action_type") or "knowledge").strip().lower()
    title = str(node.get("title") or "").strip()
    answer_text = str(node.get("answer") or "").strip()

    if action == "text" and answer_text:
        await _sender().send_text_message(wa_id, answer_text, tenant_id=tenant_id)
        return

    if action == "intent":
        intent_name = str(node.get("action_ref") or "").strip()
        try:
            from backend.services import intent_answers
            raw = intent_answers.answer_for_intent(wa_id, intent_name, tenant_id=tenant_id)
            if raw:
                from backend.faq.service import synthesize_intent_answer
                synthesized = await synthesize_intent_answer(
                    raw_content=raw,
                    intent_name=intent_name or title,
                    user_query=title,
                    tenant_id=tenant_id,
                )
                await _sender().send_text_message(wa_id, synthesized, tenant_id=tenant_id)
                return
        except Exception:
            logger.exception("TENANT_MENU_INTENT_FAILED | tenant=%s node=%s", tenant_id, node.get("id"))
        await _sender().send_text_message(
            wa_id,
            "I couldn't retrieve that information right now. Please try again shortly.",
            tenant_id=tenant_id,
        )
        return

    if action == "emergency":
        await _sender().send_text_message(
            wa_id,
            "🚨 *Emergency Support*\n\nIf this is life-threatening, call emergency services first. "
            "Share your location for the nearest help point.",
            tenant_id=tenant_id,
        )
        return

    if action == "external":
        url = str(node.get("action_ref") or "").strip()
        if url:
            await _sender().send_text_message(wa_id, f"Open: {url}", tenant_id=tenant_id)
            return

    # Default: knowledge-backed answer from tenant data.
    query = f"{title}. {str(node.get('description') or '').strip()}"
    try:
        from backend.faq.service import synthesize_intent_answer
        answer = await synthesize_intent_answer(
            raw_content="",
            intent_name=title,
            user_query=query,
            tenant_id=tenant_id,
        )
        await _sender().send_text_message(wa_id, str(answer or "").strip(), tenant_id=tenant_id)
    except Exception:
        logger.exception("TENANT_MENU_KNOWLEDGE_FAILED | tenant=%s node=%s", tenant_id, node.get("id"))
        await _sender().send_text_message(
            wa_id,
            "I couldn't retrieve that information right now. Please try again shortly.",
            tenant_id=tenant_id,
        )


async def handle_tenant_menu_action(
    wa_id: str,
    message: str,
    *,
    tenant_id: str | None,
) -> Optional[dict]:
    """Render or route a DB-backed hierarchical menu."""
    nodes = _load_nodes(tenant_id)
    if not nodes:
        return None

    text = str(message or "").strip()
    if not text:
        return None

    if text.lower() in {"menu", "main menu", "main_menu", "show options", "options"}:
        _set_current_node(wa_id, None, tenant_id=tenant_id)
        await _send_node_list(wa_id, nodes, None, tenant_id=tenant_id)
        return {"handled": True, "action": "tenant_menu_root"}

    if text == _BACK_ID:
        current = _get_current_node(wa_id, tenant_id=tenant_id)
        node = _node_by_id(nodes, current) if current else None
        parent_id = str(node.get("parent_id") or "").strip() or None if node else None
        _set_current_node(wa_id, parent_id, tenant_id=tenant_id)
        await _send_node_list(wa_id, nodes, parent_id, tenant_id=tenant_id)
        return {"handled": True, "action": "tenant_menu_back"}

    if text == _MAIN_ID:
        _set_current_node(wa_id, None, tenant_id=tenant_id)
        await _send_node_list(wa_id, nodes, None, tenant_id=tenant_id)
        return {"handled": True, "action": "tenant_menu_root"}

    if not text.startswith(_MENU_NODE_PREFIX):
        return None

    node_id = text[len(_MENU_NODE_PREFIX):].strip()
    node = _node_by_id(nodes, node_id)
    if not node:
        _set_current_node(wa_id, None, tenant_id=tenant_id)
        await _send_node_list(wa_id, nodes, None, tenant_id=tenant_id)
        return {"handled": True, "action": "tenant_menu_root"}

    children = _children_of(nodes, node_id)
    if children:
        _set_current_node(wa_id, node_id, tenant_id=tenant_id)
        await _send_node_list(wa_id, nodes, node_id, tenant_id=tenant_id)
        return {"handled": True, "action": "tenant_menu_branch", "node": node_id}

    await _answer_node(wa_id, node, tenant_id=tenant_id)
    return {"handled": True, "action": "tenant_menu_leaf", "node": node_id}