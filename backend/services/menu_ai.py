"""AI-assisted WhatsApp menu draft generation from tenant data.

The LLM proposes a hierarchical menu.  It is never allowed to invent facts:
every leaf must reference source material gathered from the tenant's own
FAQ/KB tables, and the returned JSON is validated before it is saved.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("services.menu_ai")

_ALLOWED_ACTIONS = {"knowledge", "intent", "flow", "emergency", "text", "external"}
_MAX_NODES = 40
_MAX_DEPTH = 4


def _collect_tenant_data(tenant_id: str, limit: int = 40) -> List[Dict[str, str]]:
    """Gather a compact, deduplicated sample of tenant FAQ/KB content."""
    from db.mongo import Repository

    snippets: List[Dict[str, str]] = []
    seen: set[str] = set()

    def _add(title: str, body: str, source: str) -> None:
        text = (body or "").strip()
        if not text:
            return
        key = text[:120].lower()
        if key in seen:
            return
        seen.add(key)
        snippets.append({"title": (title or "").strip()[:120], "text": text[:600], "source": source})

    # FAQ rows
    try:
        for row in Repository("faq_dataset").find({"tenant_id": tenant_id}, limit=limit):
            _add(
                str(row.get("title") or row.get("question") or row.get("source_file") or "FAQ"),
                str(row.get("content") or row.get("answer") or ""),
                f"faq:{row.get('id')}",
            )
            if len(snippets) >= limit:
                break
    except Exception as exc:
        logger.debug("MENU_AI_FAQ_LOAD_FAILED | tenant=%s | %s", tenant_id, exc)

    # KB rows
    if len(snippets) < limit:
        try:
            for row in Repository("knowledge_base").find({"tenant_id": tenant_id}, limit=limit):
                chunks = row.get("chunks_json")
                body = ""
                if isinstance(chunks, list) and chunks:
                    body = "\n".join(str(c) for c in chunks[:3])
                elif isinstance(chunks, str):
                    try:
                        import json as _json
                        parsed = _json.loads(chunks)
                        if isinstance(parsed, list):
                            body = "\n".join(str(c) for c in parsed[:3])
                    except Exception:
                        body = chunks
                if not body:
                    body = str(row.get("content") or "")
                _add(str(row.get("title") or "Knowledge"), body, f"kb:{row.get('id')}")
                if len(snippets) >= limit:
                    break
        except Exception as exc:
            logger.debug("MENU_AI_KB_LOAD_FAILED | tenant=%s | %s", tenant_id, exc)

    return snippets[:limit]


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return (base or "menu_item")[:64]


def _validate_node(node: Any, depth: int = 0, seen_ids: set[str] | None = None) -> Optional[Dict[str, Any]]:
    if seen_ids is None:
        seen_ids = set()
    if not isinstance(node, dict):
        return None
    if depth > _MAX_DEPTH:
        return None

    title = str(node.get("title") or "").strip()[:24]
    if not title:
        return None

    raw_id = str(node.get("id") or "").strip()
    node_id = _slugify(raw_id or title)
    if node_id in seen_ids:
        node_id = f"{node_id}_{len(seen_ids) + 1}"
    seen_ids.add(node_id)

    action_type = str(node.get("action_type") or "knowledge").strip().lower()
    if action_type not in _ALLOWED_ACTIONS:
        action_type = "knowledge"

    source_refs = node.get("source_refs")
    if not isinstance(source_refs, list):
        source_refs = []
    source_refs = [str(s).strip() for s in source_refs if str(s).strip()][:8]

    children_raw = node.get("children")
    children: List[Dict[str, Any]] = []
    if isinstance(children_raw, list):
        for child in children_raw[:10]:
            validated = _validate_node(child, depth + 1, seen_ids)
            if validated:
                children.append(validated)

    return {
        "id": node_id,
        "title": title,
        "description": str(node.get("description") or "").strip()[:72],
        "section": str(node.get("section") or "General").strip() or "General",
        "icon": str(node.get("icon") or "").strip()[:8],
        "sort_order": int(node.get("sort_order") or 0),
        "enabled": bool(node.get("enabled", True)),
        "requires_feature": node.get("requires_feature"),
        "out_of_hours_only": bool(node.get("out_of_hours_only", False)),
        "flow": node.get("flow"),
        "intent": node.get("intent"),
        "parent_id": None,  # filled in by _flatten
        "action_type": action_type,
        "action_ref": (str(node.get("action_ref")).strip() if node.get("action_ref") is not None else None),
        "answer": (str(node.get("answer")).strip() if node.get("answer") is not None else None),
        "source_refs": source_refs,
        "_children": children,
    }


def _flatten(nodes: List[Dict[str, Any]], parent_id: str | None = None) -> List[Dict[str, Any]]:
    """Flatten a nested tree into rows carrying ``parent_id``."""
    out: List[Dict[str, Any]] = []
    for node in nodes:
        children = node.pop("_children", [])
        node["parent_id"] = parent_id
        out.append(node)
        out.extend(_flatten(children, node["id"]))
    return out


def _normalise_draft(draft: Any) -> List[Dict[str, Any]]:
    if isinstance(draft, dict):
        if isinstance(draft.get("buttons"), list):
            draft = draft["buttons"]
        elif isinstance(draft.get("menu"), dict) and isinstance(draft["menu"].get("buttons"), list):
            draft = draft["menu"]["buttons"]
        elif isinstance(draft.get("children"), list):
            draft = draft["children"]
        else:
            draft = list(draft.values())
    if not isinstance(draft, list):
        return []
    validated: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in draft[:_MAX_NODES]:
        node = _validate_node(item, 0, seen_ids)
        if node:
            validated.append(node)
    return _flatten(validated)


def generate_menu_draft(tenant_id: str) -> Dict[str, Any]:
    """Generate and return a draft menu payload for the tenant.

    The draft is *not* published; callers decide whether to save it.
    """
    tenant_id = str(tenant_id or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required")

    data = _collect_tenant_data(tenant_id)
    if not data:
        return {
            "ok": False,
            "tenant_id": tenant_id,
            "error": "No FAQ or knowledge-base content found for this tenant. Upload data first.",
            "draft": [],
        }

    evidence = "\n\n".join(
        f"[{d['source']}] {d['title']}\n{d['text']}" for d in data
    )

    system_prompt = (
        "You are a WhatsApp menu designer. Using ONLY the tenant evidence below, "
        "propose a concise hierarchical WhatsApp menu. Return ONLY valid JSON with "
        "this exact shape:\n"
        '{"buttons":[{"id":"...","title":"...","description":"...","section":"...",'
        '"sort_order":0,"enabled":true,"action_type":"knowledge","action_ref":null,'
        '"answer":null,"source_refs":["faq:1"],"children":[]}]}\n'
        "Rules:\n"
        "- Use only information present in the evidence.\n"
        "- Titles <= 24 chars, descriptions <= 72 chars.\n"
        "- action_type must be one of: knowledge, intent, flow, emergency, text, external.\n"
        "- Prefer 'knowledge' for factual topics and 'emergency' only for real emergency/help.\n"
        "- source_refs must cite evidence labels.\n"
        "- Maximum 8 top-level items and 4 levels total.\n"
        "- Do not invent products, prices, policies, or contact details."
    )
    user_prompt = f"Tenant evidence:\n{evidence}"

    try:
        from services.auto_bifurcator import AutoBifurcator
        bifurcator = AutoBifurcator(tenant_id=tenant_id)
        raw = bifurcator._call_llm_json(system_prompt, user_prompt)
    except Exception as exc:
        logger.exception("MENU_AI_LLM_FAILED | tenant=%s", tenant_id)
        raw = None

    buttons: List[Dict[str, Any]] = []
    if isinstance(raw, dict):
        buttons = _normalise_draft(raw)
    elif isinstance(raw, list):
        buttons = _normalise_draft(raw)

    if not buttons:
        return {
            "ok": False,
            "tenant_id": tenant_id,
            "error": "AI could not generate a menu from the available data.",
            "draft": [],
            "sources": [d["source"] for d in data],
        }

    return {
        "ok": True,
        "tenant_id": tenant_id,
        "draft": buttons,
        "sources": [d["source"] for d in data],
    }
PY