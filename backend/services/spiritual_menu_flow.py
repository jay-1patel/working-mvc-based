"""Hierarchical WhatsApp menus for the spiritual tenant (PDF-aligned).

Main (events + support):
  Gangasagar · Kumbh Mela · Rath Yatra · Spiritual Guide ·
  Emergency · Lost & Found · Seva

Event tap → module list (calendar, snan, travel, stay, food, temples,
puja, programmes, medical) → topic answer.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("services.spiritual_menu_flow")


def _norm(text: str) -> str:
    cleaned = re.sub(r"[\W_]+", " ", str(text or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


# ── Event-specific modules (PDF Modules 2–9) ─────────────────────────────────

EVENT_MODULES: list[dict[str, str]] = [
    {
        "key": "calendar",
        "title": "Calendar",
        "description": "Dates, muhurat & schedules",
        "answer": (
            "📅 *Event Calendar — {event}*\n\n"
            "Key dates, auspicious muhurat, snan/darshan windows and daily "
            "programme timings will appear here once the organisers publish "
            "the approved calendar.\n\n"
            "Ask for a specific date or ceremony if you need help."
        ),
    },
    {
        "key": "snan",
        "title": "Snan Darshan",
        "description": "Holy bath & darshan info",
        "answer": (
            "🌊 *Snan & Darshan — {event}*\n\n"
            "Guidance for holy bath (snan), darshan queues, rituals and "
            "peak timings will be shared from verified event sources.\n\n"
            "Ask about today's snan window or special bathing dates."
        ),
    },
    {
        "key": "travel",
        "title": "Travel",
        "description": "Train, road, ferry & routes",
        "answer": (
            "🗺️ *Travel Assistance — {event}*\n\n"
            "Rail, road, airport and local transport options for this event "
            "will be listed here (including ferry/water routes where applicable).\n\n"
            "Tell us your starting city (e.g. Ahmedabad) for a step-by-step plan."
        ),
    },
    {
        "key": "stay",
        "title": "Stay",
        "description": "Dharamshala, hotel, shelter",
        "answer": (
            "🛏️ *Accommodation — {event}*\n\n"
            "Official dharamshalas, ashrams, guest houses, tents and "
            "senior-friendly stays will be listed from approved directories.\n\n"
            "Ask for budget, family or government lodging options."
        ),
    },
    {
        "key": "food",
        "title": "Food Prasad",
        "description": "Annadan, prasad & facilities",
        "answer": (
            "🍲 *Food, Prasad & Facilities — {event}*\n\n"
            "Annadan / bhandara points, prasad centres, drinking water, "
            "toilets, cloakrooms and parking guidance will appear here.\n\n"
            "Ask for the nearest facility type you need."
        ),
    },
    {
        "key": "temples",
        "title": "Temples",
        "description": "Temples & sacred places",
        "answer": (
            "🛕 *Temples & Places — {event}*\n\n"
            "Directory of temples, ashrams and nearby sacred spots for this "
            "event — with significance, timings and navigation tips.\n\n"
            "Ask for a specific temple or place name."
        ),
    },
    {
        "key": "puja",
        "title": "Puja Rituals",
        "description": "Puja, tarpan, daan & more",
        "answer": (
            "🙏 *Puja & Rituals — {event}*\n\n"
            "Educational guidance on puja, snan, tarpan, pind daan, "
            "surya arghya, deepdaan, sankalp and prasad.\n\n"
            "For specialised rites, we will point you to authorised priests."
        ),
    },
    {
        "key": "programmes",
        "title": "Programmes",
        "description": "Aarti, bhajan, pravachan",
        "answer": (
            "🎶 *Spiritual Programmes — {event}*\n\n"
            "Daily aarti, bhajan, kirtan, satsang, discourses and cultural "
            "programmes will be listed from the official schedule.\n\n"
            "Ask for today's aarti or evening programmes."
        ),
    },
    {
        "key": "medical",
        "title": "Medical",
        "description": "Camps, hospitals & safety",
        "answer": (
            "🏥 *Medical & Safety — {event}*\n\n"
            "Medical camps, hospital locators, ambulance contacts and "
            "crowd/weather safety notes for this event.\n\n"
            "In an emergency, call local emergency services first — then ask us for the nearest helpdesk."
        ),
    },
]

EVENTS: dict[str, dict[str, Any]] = {
    "menu_gangasagar": {
        "slug": "gangasagar",
        "title": "Gangasagar",
        "header": "Gangasagar Mela",
        "body": (
            "Gangasagar Mela — choose what you need:\n"
            "calendar, snan, travel, stay, food, temples, rituals and more."
        ),
        "place": "Sagar Island, West Bengal",
    },
    "menu_kumbh": {
        "slug": "kumbh",
        "title": "Kumbh Mela",
        "header": "Kumbh Mela",
        "body": (
            "Kumbh Mela — choose what you need:\n"
            "calendar, snan, travel, stay, food, temples, rituals and more."
        ),
        "place": "Prayagraj / Haridwar / Nashik / Ujjain",
    },
    "menu_rath_yatra": {
        "slug": "rath_yatra",
        "title": "Rath Yatra",
        "header": "Jagannath Rath Yatra",
        "body": (
            "Jagannath Rath Yatra — choose what you need:\n"
            "calendar, darshan, travel, stay, food, temples, rituals and more."
        ),
        "place": "Puri, Odisha",
    },
}

# ── Spiritual Guide topics (PDF Module 1) ────────────────────────────────────

GUIDE_TOPICS: list[dict[str, str]] = [
    {
        "key": "history",
        "title": "History",
        "description": "History & mythology",
        "answer": (
            "📜 *Religious History*\n\n"
            "Ask about the significance of Gangasagar, Kumbh, Rath Yatra, "
            "Kapil Muni, Makar Sankranti, Moksha and related traditions.\n\n"
            "Answers use approved scriptural and historical sources."
        ),
    },
    {
        "key": "scriptures",
        "title": "Scriptures",
        "description": "Hindu scriptures & teachings",
        "answer": (
            "📖 *Scriptures & Philosophy*\n\n"
            "Ask about teachings from Hindu scriptures, moksha, dharma and "
            "philosophical concepts — with clear distinction between history, "
            "scripture and traditional belief."
        ),
    },
    {
        "key": "rituals",
        "title": "Rituals",
        "description": "Traditions & customs",
        "answer": (
            "🪔 *Rituals & Customs*\n\n"
            "Learn about traditional rituals, customs and why they are performed. "
            "For specialised ceremonies, seek a qualified priest."
        ),
    },
    {
        "key": "saints",
        "title": "Saints",
        "description": "Saints & spiritual leaders",
        "answer": (
            "🧘 *Saints & Leaders*\n\n"
            "Ask about saints, sadhus, Kapil Muni and other spiritual figures "
            "connected to pilgrimage traditions."
        ),
    },
    {
        "key": "mantras",
        "title": "Mantras",
        "description": "Mantras & shlokas",
        "answer": (
            "🕉️ *Mantras & Shlokas*\n\n"
            "Ask for meanings of common mantras and shlokas used in pilgrimage "
            "and daily prayer. We share educational meanings, not claims of magical results."
        ),
    },
    {
        "key": "meditation",
        "title": "Meditation",
        "description": "Prayer & meditation",
        "answer": (
            "🕊️ *Meditation & Prayer*\n\n"
            "Ask for a short guided prayer thought or simple meditation practice "
            "suitable for pilgrims and devotees."
        ),
    },
]

# ── Direct support answers (PDF Modules 9, 10, 12) ───────────────────────────

DIRECT_ANSWERS: dict[str, dict[str, str]] = {
    "menu_emergency": {
        "title": "Emergency",
        "answer": (
            "🚨 *Emergency & Safety*\n\n"
            "If you are in danger, call local emergency services immediately.\n\n"
            "I can help with:\n"
            "• Emergency contact directory\n"
            "• Nearest medical camp / hospital\n"
            "• Police / helpdesk pointers\n"
            "• Weather & crowd safety notes\n\n"
            "Tell me your event (Gangasagar / Kumbh / Rath Yatra) and what you need."
        ),
    },
    "menu_lost_found": {
        "title": "Lost Found",
        "answer": (
            "🧭 *Lost & Found / Family Assistance*\n\n"
            "I can help you start a missing-person or lost-item report:\n"
            "• Description and last-known location\n"
            "• Photo (with consent)\n"
            "• Emergency contact\n"
            "• Case ID for tracking\n\n"
            "Reply with *missing person* or *lost item*, and your event name. "
            "Sensitive cases go to authorised helpdesk staff."
        ),
    },
    "menu_seva": {
        "title": "Seva",
        "answer": (
            "🤝 *Donation, Seva & Volunteering*\n\n"
            "Connect with authorised seva activities:\n"
            "• Annadan / Bhandara\n"
            "• Medical seva\n"
            "• Cleanliness drives\n"
            "• Volunteer registration\n\n"
            "Tell me which seva you want, and for which event."
        ),
    },
}

_MODULE_BY_KEY = {m["key"]: m for m in EVENT_MODULES}
_GUIDE_BY_KEY = {g["key"]: g for g in GUIDE_TOPICS}
_EVENT_IDS = frozenset(EVENTS.keys())
_DIRECT_IDS = frozenset(DIRECT_ANSWERS.keys())
_MAIN_IDS = _EVENT_IDS | _DIRECT_IDS | {"menu_spiritual_guide"}

_EVENT_TITLE_KEYS: dict[str, str] = {}
for _cid, _meta in EVENTS.items():
    _EVENT_TITLE_KEYS[_norm(_meta["title"])] = _cid
_EVENT_TITLE_KEYS.update({
    _norm("Gangasagar Mela"): "menu_gangasagar",
    _norm("Gangasagar"): "menu_gangasagar",
    _norm("Kumbh"): "menu_kumbh",
    _norm("Kumbh Mela"): "menu_kumbh",
    _norm("Rath Yatra"): "menu_rath_yatra",
    _norm("Jagannath Rath Yatra"): "menu_rath_yatra",
    _norm("Jagannath"): "menu_rath_yatra",
})

_DIRECT_TITLE_KEYS = {
    _norm("Emergency"): "menu_emergency",
    _norm("Lost Found"): "menu_lost_found",
    _norm("Lost & Found"): "menu_lost_found",
    _norm("Seva"): "menu_seva",
    _norm("Donation"): "menu_seva",
    _norm("Seva Donation"): "menu_seva",
}

_GUIDE_TITLE_KEYS = {
    _norm("Spiritual Guide"): "menu_spiritual_guide",
    _norm("Spiritual Knowledge"): "menu_spiritual_guide",
}


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
        return bool(ids & _MAIN_IDS)
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


async def _send_event_modules(wa_id: str, category_id: str, *, tenant_id: str | None) -> bool:
    meta = EVENTS[category_id]
    slug = meta["slug"]
    rows = []
    for mod in EVENT_MODULES:
        rows.append({
            "id": f"em_{slug}_{mod['key']}",
            "title": mod["title"][:24],
            "description": mod["description"][:72],
        })
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
        "View Options",
        _list_sections(rows, "Services"),
        tenant_id=tenant_id,
    )


async def _send_guide_menu(wa_id: str, *, tenant_id: str | None) -> bool:
    rows = []
    for topic in GUIDE_TOPICS:
        rows.append({
            "id": f"sg_{topic['key']}",
            "title": topic["title"][:24],
            "description": topic["description"][:72],
        })
    rows.append({
        "id": "main_menu",
        "title": "Main Menu",
        "description": "Back to all options",
    })
    sender = _sender()
    return await sender.send_list_menu(
        wa_id,
        "Spiritual Guide",
        "Ask about history, scriptures, rituals, saints, mantras or meditation:",
        "Topics",
        _list_sections(rows, "Guide"),
        tenant_id=tenant_id,
    )


async def _send_main(wa_id: str, *, tenant_id: str | None) -> None:
    try:
        from bots.customer_b2c.workflows import _send_main_menu
        await _send_main_menu(wa_id, tenant_id=tenant_id)
        return
    except Exception:
        pass
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


def _event_label(slug: str) -> str:
    for meta in EVENTS.values():
        if meta["slug"] == slug:
            place = meta.get("place") or ""
            return f"{meta['header']}" + (f" ({place})" if place else "")
    return slug.replace("_", " ").title()


def _parse_event_module(text: str) -> Optional[tuple[str, str]]:
    raw = str(text or "").strip()
    m = re.match(r"^em[_:]([a-z0-9_]+)_([a-z0-9]+)$", raw, re.I)
    if not m:
        return None
    slug, key = m.group(1).lower(), m.group(2).lower()
    known = {meta["slug"] for meta in EVENTS.values()}
    if slug not in known or key not in _MODULE_BY_KEY:
        return None
    return slug, key


def _parse_guide(text: str) -> Optional[str]:
    raw = str(text or "").strip()
    m = re.match(r"^sg[_:]([a-z0-9]+)$", raw, re.I)
    if m:
        key = m.group(1).lower()
        return key if key in _GUIDE_BY_KEY else None
    key = _norm(raw)
    for g in GUIDE_TOPICS:
        if _norm(g["title"]) == key:
            return g["key"]
    return None


def _match_main(text: str) -> Optional[str]:
    raw = str(text or "").strip()
    if raw in _MAIN_IDS:
        return raw
    key = _norm(raw)
    if key in _EVENT_TITLE_KEYS:
        return _EVENT_TITLE_KEYS[key]
    if key in _DIRECT_TITLE_KEYS:
        return _DIRECT_TITLE_KEYS[key]
    if key in _GUIDE_TITLE_KEYS:
        return _GUIDE_TITLE_KEYS[key]
    compact = key.replace(" ", "_")
    for cid in _MAIN_IDS:
        if compact == cid or compact == cid.replace("menu_", ""):
            return cid
    return None


def _followup_buttons(kind: str, slug: str = "") -> list[dict]:
    if kind == "event" and slug:
        return [
            {"id": f"em_{slug}_travel", "title": "Travel"},
            {"id": f"em_{slug}_stay", "title": "Stay"},
            {"id": "main_menu", "title": "Main Menu"},
        ]
    if kind == "guide":
        return [
            {"id": "menu_gangasagar", "title": "Gangasagar"},
            {"id": "menu_kumbh", "title": "Kumbh Mela"},
            {"id": "main_menu", "title": "Main Menu"},
        ]
    return [
        {"id": "menu_gangasagar", "title": "Gangasagar"},
        {"id": "menu_emergency", "title": "Emergency"},
        {"id": "main_menu", "title": "Main Menu"},
    ]


async def handle_spiritual_menu_action(
    wa_id: str,
    message: str,
    *,
    tenant_id: str | None = None,
) -> Optional[dict]:
    """Handle spiritual PDF menu taps. Returns handled dict or None."""
    if not is_spiritual_tenant(tenant_id):
        return None

    text = str(message or "").strip()
    if not text:
        return None

    if text in {"spiritual_back_categories", "spiritual_main"} or _norm(text) in {
        "all categories", "main spiritual menu",
    }:
        await _send_main(wa_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_main"}

    main_id = _match_main(text)
    if main_id in _EVENT_IDS:
        await _send_event_modules(wa_id, main_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_event", "category": main_id}

    if main_id == "menu_spiritual_guide":
        await _send_guide_menu(wa_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_guide"}

    if main_id in _DIRECT_IDS:
        payload = DIRECT_ANSWERS[main_id]
        await _sender().send_button_message(
            wa_id,
            payload["answer"],
            _followup_buttons("direct"),
            tenant_id=tenant_id,
        )
        return {"handled": True, "action": "spiritual_direct", "category": main_id}

    parsed = _parse_event_module(text)
    if parsed:
        slug, key = parsed
        mod = _MODULE_BY_KEY[key]
        answer = mod["answer"].format(event=_event_label(slug))
        await _sender().send_button_message(
            wa_id, answer, _followup_buttons("event", slug), tenant_id=tenant_id,
        )
        return {"handled": True, "action": "spiritual_event_module", "slug": slug, "topic": key}

    guide_key = _parse_guide(text)
    if guide_key:
        topic = _GUIDE_BY_KEY[guide_key]
        await _sender().send_button_message(
            wa_id, topic["answer"], _followup_buttons("guide"), tenant_id=tenant_id,
        )
        return {"handled": True, "action": "spiritual_guide_topic", "topic": guide_key}

    return None
