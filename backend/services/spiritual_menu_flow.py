"""Hierarchical WhatsApp menus for the spiritual tenant.

Main → category list → temple/yatra list → detail topics
(prasad, arti, reach, stay, benefit, history, parking).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("services.spiritual_menu_flow")

# ── Detail topics shown after a temple / yatra is chosen ─────────────────────

DETAIL_TOPICS: list[dict[str, str]] = [
    {
        "key": "prasad",
        "title": "Prasad",
        "description": "Prasad offerings & timings",
        "answer": (
            "🛕 *Prasad — {name}*\n\n"
            "Blessed prasad is distributed after morning and evening arti.\n"
            "Timings and special bhog days vary by festival — ask if you need today's schedule."
        ),
    },
    {
        "key": "arti",
        "title": "Arti",
        "description": "Daily arti schedule",
        "answer": (
            "🪔 *Arti Time — {name}*\n\n"
            "Morning and evening arti are offered daily.\n"
            "Exact slots change on festival days — ask for today's morning or evening time."
        ),
    },
    {
        "key": "reach",
        "title": "Reach",
        "description": "How to reach",
        "answer": (
            "🗺️ *How to Reach — {name}*\n\n"
            "Nearest rail / road links serve this sacred place.\n"
            "Open Maps for turn-by-turn directions, or ask for the closest station/airport."
        ),
    },
    {
        "key": "stay",
        "title": "Stay",
        "description": "Where to stay",
        "answer": (
            "🛏️ *Where to Stay — {name}*\n\n"
            "Dharamshalas, guest houses, and hotels are available nearby.\n"
            "Book early in peak yatra season. Ask if you need budget or family stay options."
        ),
    },
    {
        "key": "advantage",
        "title": "Benefit",
        "description": "Spiritual benefits",
        "answer": (
            "✨ *Advantage — {name}*\n\n"
            "A visit brings darshan, peace, and an opportunity for seva and charity.\n"
            "Many devotees also offer prayers for family wellbeing here."
        ),
    },
    {
        "key": "history",
        "title": "History",
        "description": "Sacred history",
        "answer": (
            "📜 *History — {name}*\n\n"
            "This is among India's revered pilgrimage destinations, with centuries of devotion.\n"
            "Ask if you want the legend, architecture notes, or festival heritage."
        ),
    },
    {
        "key": "vehicle",
        "title": "Parking",
        "description": "Vehicle & parking",
        "answer": (
            "🚗 *Vehicle Type — {name}*\n\n"
            "Car, two-wheeler, and bus parking are usually available near the approach road.\n"
            "Large vehicles may need designated lots — ask for peak-hour parking tips."
        ),
    },
]

# ── Destinations (temples / yatras) ──────────────────────────────────────────

NORTH_TEMPLES = [
    {"slug": "somnath", "title": "Somnath", "place": "Gujarat"},
    {"slug": "dwarka", "title": "Dwarka", "place": "Gujarat"},
    {"slug": "ambaji", "title": "Ambaji", "place": "Gujarat"},
    {"slug": "kashi", "title": "Kashi", "place": "Varanasi, UP"},
    {"slug": "kedarnath", "title": "Kedarnath", "place": "Uttarakhand"},
    {"slug": "badrinath", "title": "Badrinath", "place": "Uttarakhand"},
    {"slug": "vaishnodevi", "title": "Vaishno Devi", "place": "Jammu"},
]

SOUTH_TEMPLES = [
    {"slug": "tirupati", "title": "Tirupati", "place": "Andhra Pradesh"},
    {"slug": "meenakshi", "title": "Meenakshi", "place": "Madurai, TN"},
    {"slug": "rameswaram", "title": "Rameswaram", "place": "Tamil Nadu"},
    {"slug": "brihadeeswar", "title": "Brihadeeswar", "place": "Thanjavur, TN"},
    {"slug": "padmanabha", "title": "Padmanabha", "place": "Kerala"},
    {"slug": "sabarimala", "title": "Sabarimala", "place": "Kerala"},
    {"slug": "shirdi", "title": "Shirdi", "place": "Maharashtra"},
]

NORTH_PILGRIMAGE = [
    {"slug": "chardham_uk", "title": "Char Dham UK", "place": "Uttarakhand"},
    {"slug": "kashi_yatra", "title": "Kashi Yatra", "place": "Varanasi"},
    {"slug": "vaishno_yatra", "title": "Vaishno Yatra", "place": "Jammu"},
    {"slug": "somnath_dwarka", "title": "Somnath-Dwarka", "place": "Gujarat"},
    {"slug": "ambaji_yatra", "title": "Ambaji Yatra", "place": "Gujarat"},
    {"slug": "amarnath", "title": "Amarnath", "place": "Kashmir"},
    {"slug": "mathura_vrindavan", "title": "Mathura-Vrindavan", "place": "UP"},
]

SOUTH_PILGRIMAGE = [
    {"slug": "tirupati_yatra", "title": "Tirupati Yatra", "place": "Andhra"},
    {"slug": "rameswaram_yatra", "title": "Rameswaram", "place": "Tamil Nadu"},
    {"slug": "madurai_yatra", "title": "Madurai Yatra", "place": "Tamil Nadu"},
    {"slug": "sabarimala_yatra", "title": "Sabarimala", "place": "Kerala"},
    {"slug": "padmanabha_yatra", "title": "Padmanabha", "place": "Kerala"},
    {"slug": "shirdi_yatra", "title": "Shirdi Yatra", "place": "Maharashtra"},
    {"slug": "pandharpur", "title": "Pandharpur", "place": "Maharashtra"},
]

FOUR_DHAM = [
    {"slug": "badrinath_dham", "title": "Badrinath", "place": "Uttarakhand"},
    {"slug": "dwarka_dham", "title": "Dwarka", "place": "Gujarat"},
    {"slug": "puri_dham", "title": "Jagannath Puri", "place": "Odisha"},
    {"slug": "rameswaram_dham", "title": "Rameswaram", "place": "Tamil Nadu"},
]

GUJARAT_TEMPLES = [
    {"slug": "somnath_gj", "title": "Somnath", "place": "Veraval"},
    {"slug": "dwarka_gj", "title": "Dwarka", "place": "Devbhoomi Dwarka"},
    {"slug": "ambaji_gj", "title": "Ambaji", "place": "Banaskantha"},
    {"slug": "pavagadh", "title": "Pavagadh", "place": "Panchmahal"},
    {"slug": "akshardham_gj", "title": "Akshardham", "place": "Gandhinagar"},
    {"slug": "modhera", "title": "Modhera Sun", "place": "Mehsana"},
    {"slug": "bahucharaji", "title": "Bahucharaji", "place": "Mehsana"},
]

CATEGORIES: dict[str, dict[str, Any]] = {
    "menu_north_temples": {
        "title": "North Temples",
        "header": "North Temples",
        "body": "Choose a North India temple:",
        "items": NORTH_TEMPLES,
    },
    "menu_south_temples": {
        "title": "South Temples",
        "header": "South Temples",
        "body": "Choose a South India temple:",
        "items": SOUTH_TEMPLES,
    },
    "menu_north_yatra": {
        "title": "North Yatra",
        "header": "North Pilgrimage",
        "body": "Choose a North India pilgrimage:",
        "items": NORTH_PILGRIMAGE,
    },
    "menu_south_yatra": {
        "title": "South Yatra",
        "header": "South Pilgrimage",
        "body": "Choose a South India pilgrimage:",
        "items": SOUTH_PILGRIMAGE,
    },
    "menu_4_dham": {
        "title": "4 Dham",
        "header": "Char Dham",
        "body": "Choose one of the four dhams:",
        "items": FOUR_DHAM,
    },
    "menu_gujarat": {
        "title": "Gujarat",
        "header": "Famous Gujarat Temples",
        "body": "Choose a famous Gujarat temple:",
        "items": GUJARAT_TEMPLES,
    },
}


def _norm(text: str) -> str:
    cleaned = re.sub(r"[\W_]+", " ", str(text or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


# Flatten slug → destination meta
_DEST_BY_SLUG: dict[str, dict[str, str]] = {}
for _cat in CATEGORIES.values():
    for _item in _cat["items"]:
        _DEST_BY_SLUG[str(_item["slug"])] = {
            "slug": str(_item["slug"]),
            "title": str(_item["title"]),
            "place": str(_item.get("place") or ""),
        }

_TOPIC_BY_KEY = {t["key"]: t for t in DETAIL_TOPICS}

_CATEGORY_IDS = frozenset(CATEGORIES.keys())
_CATEGORY_TITLE_KEYS = {
    _norm(meta["title"]): cid for cid, meta in CATEGORIES.items()
}
# Extra title aliases for Send2 plain-title taps
_CATEGORY_TITLE_KEYS.update({
    _norm("North Temples"): "menu_north_temples",
    _norm("South Temples"): "menu_south_temples",
    _norm("North Pilgrimage"): "menu_north_yatra",
    _norm("South Pilgrimage"): "menu_south_yatra",
    _norm("North Yatra"): "menu_north_yatra",
    _norm("South Yatra"): "menu_south_yatra",
    _norm("4 Dham"): "menu_4_dham",
    _norm("Char Dham"): "menu_4_dham",
    _norm("Famous Temple of Gujarat"): "menu_gujarat",
    _norm("Gujarat Temples"): "menu_gujarat",
    _norm("Gujarat"): "menu_gujarat",
})


def is_spiritual_tenant(tenant_id: str | None) -> bool:
    tid = str(tenant_id or "").strip().lower()
    if tid in {"spiritual", "temple", "aastha"}:
        return True
    try:
        from shared.tenancy.loader import get_tenant_profile

        profile = get_tenant_profile(tid)
        ids = {
            str(getattr(b, "id", "") or "")
            for b in (getattr(getattr(profile, "menu", None), "buttons", None) or [])
        }
        return bool(ids & _CATEGORY_IDS)
    except Exception:
        return False


def _sender():
    try:
        from services import whatsapp_sender as sender
    except ImportError:
        from backend.services import whatsapp_sender as sender
    return sender


def _list_sections(rows: list[dict[str, str]], section_title: str = "Options") -> list[dict]:
    return [{
        "title": section_title[:24],
        "rows": [
            {
                "id": r["id"][:200],
                "title": r["title"][:24],
                "description": (r.get("description") or "")[:72],
            }
            for r in rows[:10]
        ],
    }]


async def _send_destination_list(
    wa_id: str,
    category_id: str,
    *,
    tenant_id: str | None,
) -> bool:
    meta = CATEGORIES[category_id]
    rows = []
    for item in meta["items"][:10]:
        place = item.get("place") or ""
        rows.append({
            "id": f"tpl_{item['slug']}",
            "title": str(item["title"])[:24],
            "description": place[:72],
        })
    # Back to main
    rows.append({
        "id": "main_menu",
        "title": "Main Menu",
        "description": "Back to all options",
    })
    sender = _sender()
    return await sender.send_list_menu(
        wa_id,
        str(meta["header"])[:60],
        str(meta["body"])[:1024],
        "View List",
        _list_sections(rows, "Choose"),
        tenant_id=tenant_id,
    )


async def _send_detail_menu(
    wa_id: str,
    slug: str,
    *,
    tenant_id: str | None,
) -> bool:
    dest = _DEST_BY_SLUG.get(slug) or {"slug": slug, "title": slug.replace("_", " ").title(), "place": ""}
    name = dest["title"]
    place = dest.get("place") or ""
    rows = []
    for topic in DETAIL_TOPICS:
        rows.append({
            "id": f"td_{slug}_{topic['key']}",
            "title": topic["title"][:24],
            "description": topic["description"][:72],
        })
    rows.append({
        "id": "spiritual_back_categories",
        "title": "All Categories",
        "description": "Back to main spiritual menu",
    })
    body = f"*{name}*"
    if place:
        body += f"\n_{place}_"
    body += "\n\nWhat would you like to know?"
    sender = _sender()
    return await sender.send_list_menu(
        wa_id,
        name[:60],
        body[:1024],
        "Options",
        _list_sections(rows, "Details"),
        tenant_id=tenant_id,
    )


def _detail_answer(slug: str, topic_key: str) -> str:
    dest = _DEST_BY_SLUG.get(slug) or {
        "title": slug.replace("_", " ").title(),
        "place": "",
    }
    topic = _TOPIC_BY_KEY.get(topic_key) or DETAIL_TOPICS[0]
    name = dest["title"]
    place = dest.get("place") or ""
    label = f"{name}" + (f" ({place})" if place else "")
    return str(topic["answer"]).format(name=label)


def _match_category(text: str) -> Optional[str]:
    raw = str(text or "").strip()
    if raw in _CATEGORY_IDS:
        return raw
    key = _norm(raw)
    if key in _CATEGORY_TITLE_KEYS:
        return _CATEGORY_TITLE_KEYS[key]
    # id without menu_ prefix
    compact = key.replace(" ", "_")
    for cid in _CATEGORY_IDS:
        if compact == cid or compact == cid.replace("menu_", ""):
            return cid
    return None


def _parse_tpl(text: str) -> Optional[str]:
    raw = str(text or "").strip()
    m = re.match(r"^tpl[_:]([a-z0-9_]+)$", raw, re.I)
    if m:
        slug = m.group(1).lower()
        return slug if slug in _DEST_BY_SLUG else None
    # title match
    key = _norm(raw)
    for slug, dest in _DEST_BY_SLUG.items():
        if _norm(dest["title"]) == key:
            return slug
    return None


def _parse_detail(text: str) -> Optional[tuple[str, str]]:
    raw = str(text or "").strip()
    m = re.match(r"^td[_:]([a-z0-9_]+)_([a-z0-9]+)$", raw, re.I)
    if not m:
        return None
    slug, topic = m.group(1).lower(), m.group(2).lower()
    if slug not in _DEST_BY_SLUG:
        return None
    if topic not in _TOPIC_BY_KEY:
        # allow arti_time alias
        aliases = {"arti_time": "arti", "how_to_reach": "reach", "where_to_stay": "stay",
                   "advantage": "advantage", "history": "history", "vehicle_type": "vehicle",
                   "parking": "vehicle", "benefit": "advantage"}
        topic = aliases.get(topic, topic)
    if topic not in _TOPIC_BY_KEY:
        return None
    return slug, topic


async def handle_spiritual_menu_action(
    wa_id: str,
    message: str,
    *,
    tenant_id: str | None = None,
) -> Optional[dict]:
    """Handle spiritual category / temple / detail taps. Returns handled dict or None."""
    if not is_spiritual_tenant(tenant_id):
        return None

    text = str(message or "").strip()
    if not text:
        return None

    # Back to main categories
    if text in {"spiritual_back_categories", "spiritual_main"} or _norm(text) in {
        "all categories", "main spiritual menu",
    }:
        try:
            from bots.customer_b2c.workflows import _send_main_menu
            await _send_main_menu(wa_id, tenant_id=tenant_id)
        except Exception:
            from app.services.whatsapp.flows.customer_b2c.menus import get_main_menu
            payload = get_main_menu(wa_id, tenant_id=tenant_id)
            sender = _sender()
            if payload.get("type") == "buttons":
                await sender.send_button_message(
                    wa_id, payload.get("text", "Options"), payload.get("buttons", []),
                    tenant_id=tenant_id,
                )
            else:
                await sender.send_list_menu(
                    wa_id,
                    payload.get("header", ""),
                    payload.get("body", "Choose an option"),
                    payload.get("button_text", "Show Options"),
                    payload.get("sections", []),
                    tenant_id=tenant_id,
                )
        return {"handled": True, "action": "spiritual_main"}

    category_id = _match_category(text)
    if category_id:
        await _send_destination_list(wa_id, category_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_category", "category": category_id}

    slug = _parse_tpl(text)
    if slug:
        await _send_detail_menu(wa_id, slug, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_temple", "slug": slug}

    parsed = _parse_detail(text)
    if parsed:
        slug, topic = parsed
        answer = _detail_answer(slug, topic)
        sender = _sender()
        # Follow-up: other details + main menu (max 3 reply buttons)
        buttons = [
            {"id": f"td_{slug}_prasad", "title": "Prasad"},
            {"id": f"td_{slug}_arti", "title": "Arti"},
            {"id": "main_menu", "title": "Main Menu"},
        ]
        # Prefer contextual siblings for the topic just opened
        if topic == "prasad":
            buttons = [
                {"id": f"td_{slug}_arti", "title": "Arti"},
                {"id": f"td_{slug}_reach", "title": "Reach"},
                {"id": "main_menu", "title": "Main Menu"},
            ]
        elif topic in {"arti"}:
            buttons = [
                {"id": f"td_{slug}_prasad", "title": "Prasad"},
                {"id": f"td_{slug}_reach", "title": "Reach"},
                {"id": "main_menu", "title": "Main Menu"},
            ]
        elif topic in {"reach", "stay", "vehicle"}:
            buttons = [
                {"id": f"td_{slug}_stay", "title": "Stay"},
                {"id": f"td_{slug}_vehicle", "title": "Parking"},
                {"id": "main_menu", "title": "Main Menu"},
            ]
        elif topic in {"history", "advantage"}:
            buttons = [
                {"id": f"td_{slug}_advantage", "title": "Benefit"},
                {"id": f"td_{slug}_history", "title": "History"},
                {"id": "main_menu", "title": "Main Menu"},
            ]
        await sender.send_button_message(wa_id, answer, buttons, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_detail", "slug": slug, "topic": topic}

    return None
