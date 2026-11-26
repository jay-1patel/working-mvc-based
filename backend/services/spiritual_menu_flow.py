"""Hierarchical WhatsApp menus for the spiritual tenant.

Main: Kumbh Mela · Gangasagar Mela · Jagannath Rath Yatra
Events open platform components with event-specific answers. Rath Yatra omits
Holy Bathing Info:
  AI Spiritual Guide · Religious Knowledge · Religious Calendar ·
  Travel Assistance · Accommodation · Emergency Support
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("services.spiritual_menu_flow")


def _norm(text: str) -> str:
    cleaned = re.sub(r"[\W_]+", " ", str(text or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


# ── Events (main menu) ───────────────────────────────────────────────────────

EVENTS: dict[str, dict[str, Any]] = {
    "menu_kumbh": {
        "slug": "kumbh",
        "title": "Kumbh Mela",
        "header": "Kumbh Mela",
        "body": "Choose a Kumbh Mela service:",
        "event_label": "Kumbh Mela",
    },
    "menu_gangasagar": {
        "slug": "gangasagar",
        "title": "Gangasagar Mela",
        "header": "Gangasagar Mela",
        "body": "Choose a Gangasagar Mela service:",
        "event_label": "Gangasagar Mela",
    },
    "menu_rath_yatra": {
        "slug": "rath_yatra",
        "title": "Jagannath Rath Yatra",
        "header": "Jagannath Rath Yatra",
        "body": "Choose a Rath Yatra service:",
        "event_label": "Jagannath Rath Yatra",
    },
}

# ── Sub-menu (platform components) ──────────────────────────────────────────

EVENT_TOPICS: list[dict[str, Any]] = [
    {
        "key": "guide",
        "title": "AI Spiritual Guide",
        "description": "Common spiritual guidance",
        "kind": "text",
        "answers": {
            "kumbh": (
                "🙏 *AI Spiritual Guide — Kumbh Mela*\n\n"
                "Ask about sankalp, snan etiquette, mantras, or how to plan "
                "your Kumbh day with calm and devotion.\n\n"
                "Type your question anytime."
            ),
            "gangasagar": (
                "🙏 *AI Spiritual Guide — Gangasagar Mela*\n\n"
                "Ask about Kapil Muni darshan, snan sankalp, or how to keep "
                "your Gangasagar yatra peaceful and safe.\n\n"
                "Type your question anytime."
            ),
            "rath_yatra": (
                "🙏 *AI Spiritual Guide — Jagannath Rath Yatra*\n\n"
                "Ask about darshan, chariot pull etiquette, or the meaning of "
                "Rath Yatra rituals in Puri.\n\n"
                "Type your question anytime."
            ),
        },
    },
    {
        "key": "knowledge",
        "title": "Religious Knowledge",
        "description": "Event-specific sacred knowledge",
        "kind": "text",
        "answers": {
            "kumbh": (
                "📜 *Religious Knowledge — Kumbh Mela*\n\n"
                "Kumbh-specific heritage: four sacred cities, Amrit Snan cycles, "
                "akhara traditions and the spiritual meaning of the Sangam.\n\n"
                "Ask for mythology, history, or rituals."
            ),
            "gangasagar": (
                "📜 *Religious Knowledge — Gangasagar Mela*\n\n"
                "Gangasagar-specific heritage: Kapil Muni, Ganga-Sagar sangam, "
                "Makar Sankranti snan and local pilgrimage customs.\n\n"
                "Ask for mythology, history, or rituals."
            ),
            "rath_yatra": (
                "📜 *Religious Knowledge — Jagannath Rath Yatra*\n\n"
                "Rath Yatra-specific heritage: Jagannath, Balabhadra, Subhadra, "
                "Gundicha yatra and the meaning of the chariots.\n\n"
                "Ask for mythology, history, or rituals."
            ),
        },
    },
    {
        "key": "calendar",
        "title": "Religious Calendar",
        "description": "Event schedule & key dates",
        "kind": "text",
        "answers": {
            "kumbh": (
                "📅 *Religious Calendar — Kumbh*\n\n"
                "Kumbh schedule highlights: Shahi Snan / Amrit Snan dates, "
                "parikrama windows and peak crowd days (verify with official mela notice).\n\n"
                "Ask which city (Prayagraj / Haridwar / Nashik / Ujjain)."
            ),
            "gangasagar": (
                "📅 *Religious Calendar — Gangasagar*\n\n"
                "Mela schedule highlights: Makar Sankranti snan day, "
                "approach dates and ferry / snan windows "
                "(verify with official mela notice)."
            ),
            "rath_yatra": (
                "📅 *Religious Calendar — Rath Yatra*\n\n"
                "Rath Yatra schedule highlights: Snana Yatra, Gundicha, "
                "Bahuda Yatra and return dates "
                "(verify with Sri Jagannath Temple / official notice)."
            ),
        },
    },
    {
        "key": "bathing",
        "title": "Holy Bathing Info",
        "description": "Snan / ritual bathing guidance",
        "kind": "text",
        "answers": {
            "kumbh": (
                "🛁 *Holy Bathing — Kumbh*\n\n"
                "Snan locations and guidance for Kumbh ghats (Sangam and city-specific snan points). "
                "Follow local volunteers for safe entry/exit.\n\n"
                "Ask which ghat or city you are visiting."
            ),
            "gangasagar": (
                "🛁 *Holy Bathing — Gangasagar*\n\n"
                "Sangam snan guidance near Kapil Muni / main snan ghat. "
                "Mind tides, ferry timings and crowd flow.\n\n"
                "Ask for morning snan tips if needed."
            ),
            "rath_yatra": (
                "🛁 *Holy Bathing / Rituals — Rath Yatra*\n\n"
                "Applicable rituals around Jagannath Rath Yatra "
                "(Snana Yatra, chariot procession etiquette). "
                "Follow temple / police guidance on Bada Danda."
            ),
        },
    },
    {
        "key": "travel",
        "title": "Travel Assistance",
        "description": "How to reach the event",
        "kind": "text",
        "answers": {
            "kumbh": (
                "🗺️ *Travel Assistance — Kumbh*\n\n"
                "Event-specific travel: nearest rail/road for your Kumbh city, "
                "shuttle tips and peak-day advice.\n\n"
                "Tell us your starting city."
            ),
            "gangasagar": (
                "🗺️ *Travel Assistance — Gangasagar*\n\n"
                "Event-specific travel: how to reach via Kakdwip / Kachuberia, "
                "ferry and last-mile tips.\n\n"
                "Tell us your starting city."
            ),
            "rath_yatra": (
                "🗺️ *Travel Assistance — Rath Yatra*\n\n"
                "Event-specific travel: reaching Puri (rail/road), "
                "Bada Danda access and crowd-day tips.\n\n"
                "Tell us your starting city."
            ),
        },
    },
    {
        "key": "stay",
        "title": "Accommodation",
        "description": "Local stay options",
        "kind": "text",
        "answers": {
            "kumbh": (
                "🛏️ *Accommodation — Kumbh*\n\n"
                "Local facilities: tent cities, dharamshalas, ashrams and hotels "
                "near the mela zone (book early for Shahi Snan days)."
            ),
            "gangasagar": (
                "🛏️ *Accommodation — Gangasagar*\n\n"
                "Local facilities: ashrams, dharamshalas and lodges near the mela / jetty approach. "
                "Book ahead for Makar Sankranti."
            ),
            "rath_yatra": (
                "🛏️ *Accommodation — Rath Yatra*\n\n"
                "Local facilities: hotels, dharamshalas and lodges in Puri "
                "(near temple / beach / railway). Book early for yatra week."
            ),
        },
    },
    {
        "key": "emergency",
        "title": "Emergency Support",
        "description": "Local authorities & help pins",
        "kind": "emergency",
        "answers": {},
    },
]

EMERGENCY_ACTIONS: list[dict[str, str]] = [
    {"key": "medical", "title": "Medical Camp", "description": "Share GPS for nearest camp"},
    {"key": "police", "title": "Police Desk", "description": "Share GPS for nearest desk"},
    {"key": "ambulance", "title": "Ambulance", "description": "Share GPS for ambulance"},
    {"key": "women", "title": "Women Child", "description": "Share GPS for helpdesk"},
    {"key": "sharearea", "title": "Share Location", "description": "WhatsApp location → nearest help"},
]

# Facilities live in Mongo ``event_facilities`` (tenant_id, event, type, name,
# lat/lng, address, message). Seed via scripts/seed_event_facilities.py.

_TOPIC_BY_KEY = {t["key"]: t for t in EVENT_TOPICS}
_EVENT_IDS = frozenset(EVENTS.keys())
_EVENT_BY_SLUG = {str(v["slug"]): k for k, v in EVENTS.items()}

_EVENT_TITLE_KEYS: dict[str, str] = {}
for _cid, _meta in EVENTS.items():
    _EVENT_TITLE_KEYS[_norm(_meta["title"])] = _cid
_EVENT_TITLE_KEYS.update({
    _norm("Kumbh"): "menu_kumbh",
    _norm("Kumbh Mela"): "menu_kumbh",
    _norm("Gangasagar"): "menu_gangasagar",
    _norm("Gangasagar Mela"): "menu_gangasagar",
    _norm("Rath Yatra"): "menu_rath_yatra",
    _norm("Jagannath Rath Yatra"): "menu_rath_yatra",
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
        return bool(ids & _EVENT_IDS)
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


def _set_pending(wa_id: str, payload: dict, *, tenant_id: str | None) -> None:
    try:
        from database import update_user_context
        update_user_context(wa_id, {"spiritual_pending": payload}, tenant_id=tenant_id)
    except Exception:
        logger.debug("spiritual_pending save skipped", exc_info=True)


def _get_pending(wa_id: str, *, tenant_id: str | None) -> dict:
    try:
        from database import get_user_state
        row = get_user_state(wa_id, tenant_id=tenant_id) or {}
        import json
        ctx = row.get("context") if isinstance(row, dict) else None
        if isinstance(ctx, str):
            ctx = json.loads(ctx or "{}")
        pending = (ctx or {}).get("spiritual_pending") or {}
        return pending if isinstance(pending, dict) else {}
    except Exception:
        logger.debug("spiritual_pending load skipped", exc_info=True)
        return {}


def _clear_pending(wa_id: str, *, tenant_id: str | None) -> None:
    _set_pending(wa_id, {}, tenant_id=tenant_id)


def _set_active_event(wa_id: str, event_slug: str, *, tenant_id: str | None) -> None:
    """Remember the event whose title-only list replies should be resolved."""
    try:
        from database import update_user_context
        update_user_context(wa_id, {"spiritual_active_event": event_slug}, tenant_id=tenant_id)
    except Exception:
        logger.debug("spiritual active event save skipped", exc_info=True)


def _get_active_event(wa_id: str, *, tenant_id: str | None) -> str:
    try:
        from database import get_user_state
        row = get_user_state(wa_id, tenant_id=tenant_id) or {}
        import json
        ctx = row.get("context") if isinstance(row, dict) else None
        if isinstance(ctx, str):
            ctx = json.loads(ctx or "{}")
        slug = str((ctx or {}).get("spiritual_active_event") or "")
        return slug if slug in _EVENT_BY_SLUG else ""
    except Exception:
        logger.debug("spiritual active event load skipped", exc_info=True)
        return ""


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * r * asin(sqrt(a))


def _normalize_facility_row(row: dict) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "key": str(row.get("type") or row.get("key") or ""),
        "name": str(row.get("name") or ""),
        "address": str(row.get("address") or ""),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "message": str(row.get("message") or ""),
        "event": str(row.get("event") or ""),
        "tenant_id": str(row.get("tenant_id") or ""),
    }


def _facilities_for(
    event_slug: str,
    category: str | None = None,
    *,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    tid = str(tenant_id or "spiritual").strip() or "spiritual"
    try:
        from db.event_facilities import list_event_facilities
    except ImportError:
        from backend.db.event_facilities import list_event_facilities
    try:
        rows = list_event_facilities(
            tid,
            event=str(event_slug or "").strip(),
            facility_type=str(category).strip() if category else None,
            active_only=True,
        )
    except Exception:
        logger.exception("event_facilities load failed | tenant=%s event=%s", tid, event_slug)
        return []
    return [_normalize_facility_row(r) for r in rows]


def find_nearest_facility(
    event_slug: str,
    latitude: float,
    longitude: float,
    *,
    category: str | None = None,
    tenant_id: str | None = None,
) -> Optional[tuple[dict[str, Any], float]]:
    best = None
    best_km = None
    for fac in _facilities_for(event_slug, category, tenant_id=tenant_id):
        try:
            km = _haversine_km(
                float(latitude),
                float(longitude),
                float(fac["latitude"]),
                float(fac["longitude"]),
            )
        except (TypeError, ValueError, KeyError):
            continue
        if best_km is None or km < best_km:
            best = fac
            best_km = km
    if best is None or best_km is None:
        return None
    return best, best_km


async def _send_facility_pin(
    wa_id: str,
    facility: dict[str, Any],
    *,
    tenant_id: str | None,
    distance_km: float | None = None,
) -> bool:
    msg = str(facility.get("message") or "Location pin")
    if distance_km is not None:
        msg = f"{msg}\n\n_Approx. {distance_km:.1f} km from your shared location._"
    return await _sender().send_location_message(
        wa_id,
        msg,
        tenant_id=tenant_id,
        latitude=facility.get("latitude"),
        longitude=facility.get("longitude"),
        name=facility.get("name"),
        address=facility.get("address"),
    )


async def _send_pin(
    wa_id: str,
    *,
    tenant_id: str | None,
    event_slug: str,
    pin_key: str,
) -> bool:
    rows = _facilities_for(event_slug, pin_key, tenant_id=tenant_id)
    if not rows:
        await _sender().send_button_message(
            wa_id,
            "Location pin will appear once organisers publish verified coordinates.",
            [{"id": "main_menu", "title": "Main Menu"}],
            tenant_id=tenant_id,
        )
        return False
    return await _send_facility_pin(wa_id, rows[0], tenant_id=tenant_id)


async def _ask_share_whatsapp_location(
    wa_id: str,
    *,
    tenant_id: str | None,
    event_slug: str,
    category: str,
) -> None:
    labels = {
        "medical": "nearest medical camp",
        "police": "nearest police / helpdesk",
        "ambulance": "nearest ambulance point",
        "women": "nearest women & child helpdesk",
        "any": "nearest emergency help",
    }
    label = labels.get(category, "nearest help point")
    _set_pending(
        wa_id,
        {
            "kind": "await_location",
            "event_slug": event_slug,
            "place_slug": "event",
            "category": category,
        },
        tenant_id=tenant_id,
    )
    await _sender().send_button_message(
        wa_id,
        (
            f"📍 *Share your WhatsApp location*\n\n"
            f"To find the *{label}* for this event:\n"
            "1. Tap 📎 (attach)\n"
            "2. Choose *Location*\n"
            "3. Send your current location\n\n"
            "If this is life-threatening, call local emergency services first."
        ),
        [{"id": "main_menu", "title": "Main Menu"}],
        tenant_id=tenant_id,
    )


async def handle_shared_location(
    wa_id: str,
    latitude: float,
    longitude: float,
    *,
    tenant_id: str | None = None,
    name: str = "",
    address: str = "",
) -> Optional[dict]:
    if not is_spiritual_tenant(tenant_id):
        return None
    pending = _get_pending(wa_id, tenant_id=tenant_id)
    if str(pending.get("kind") or "") != "await_location":
        return None

    event_slug = str(pending.get("event_slug") or "")
    category = str(pending.get("category") or "any")
    if not event_slug:
        return None

    cat = None if category in {"", "any"} else category
    found = find_nearest_facility(
        event_slug, latitude, longitude, category=cat, tenant_id=tenant_id,
    )
    if not found and cat:
        found = find_nearest_facility(
            event_slug, latitude, longitude, category=None, tenant_id=tenant_id,
        )
    if not found:
        await _sender().send_button_message(
            wa_id,
            "Could not find a help point for this event yet. Please contact the mela helpdesk.",
            [{"id": "main_menu", "title": "Main Menu"}],
            tenant_id=tenant_id,
        )
        _clear_pending(wa_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_location_no_facility"}

    facility, km = found
    _clear_pending(wa_id, tenant_id=tenant_id)
    where = f"{name or address}".strip()
    preface = (
        f"📍 Got your location"
        + (f" ({where})" if where else "")
        + f".\nNearest: *{facility.get('name')}* (~{km:.1f} km).\n"
        "Pin is shared above."
    )
    await _send_facility_pin(
        wa_id, facility, tenant_id=tenant_id, distance_km=km,
    )
    await _sender().send_button_message(
        wa_id,
        preface,
        _event_followup_buttons(event_slug),
        tenant_id=tenant_id,
    )
    return {
        "handled": True,
        "action": "spiritual_nearest_pin",
        "facility": facility.get("name"),
        "km": km,
        "category": facility.get("key"),
    }


def _event_followup_buttons(event_slug: str) -> list[dict]:
    menu_id = _EVENT_BY_SLUG.get(event_slug) or "main_menu"
    return [
        {"id": f"st_{event_slug}_emergency", "title": "Emergency"},
        {"id": menu_id, "title": "Event Menu"},
        {"id": "main_menu", "title": "Main Menu"},
    ]


async def _send_event_topics(
    wa_id: str,
    category_id: str,
    *,
    tenant_id: str | None,
) -> bool:
    meta = EVENTS[category_id]
    slug = str(meta["slug"])
    _set_active_event(wa_id, slug, tenant_id=tenant_id)
    rows = []
    for topic in EVENT_TOPICS:
        if slug == "rath_yatra" and topic["key"] == "bathing":
            continue
        rows.append({
            "id": f"st_{slug}_{topic['key']}",
            "title": str(topic["title"])[:24],
            "description": str(topic.get("description") or "")[:72],
        })
    rows.append({
        "id": "main_menu",
        "title": "Main Menu",
        "description": "Back to all events",
    })
    return await _sender().send_list_menu(
        wa_id,
        str(meta["header"])[:60],
        str(meta["body"])[:1024],
        "Services",
        _list_sections(rows, "Services"),
        tenant_id=tenant_id,
    )


async def _send_emergency_menu(
    wa_id: str,
    event_slug: str,
    *,
    tenant_id: str | None,
) -> bool:
    meta = EVENTS.get(_EVENT_BY_SLUG.get(event_slug, ""), {}) or {}
    label = meta.get("event_label") or event_slug
    rows = []
    for act in EMERGENCY_ACTIONS:
        rows.append({
            "id": f"sea_{event_slug}_event_{act['key']}",
            "title": act["title"][:24],
            "description": act["description"][:72],
        })
    rows.append({
        "id": _EVENT_BY_SLUG.get(event_slug, "main_menu"),
        "title": "Back",
        "description": "Back to event services",
    })
    body = (
        f"🚨 *Emergency Support — {label}*\n\n"
        "Local authorities & help pins. If life-threatening, "
        "call emergency services first.\n"
        "Choose an option:"
    )
    return await _sender().send_list_menu(
        wa_id,
        "Emergency Support",
        body[:1024],
        "Options",
        _list_sections(rows, "Emergency"),
        tenant_id=tenant_id,
    )


def _match_event(text: str) -> Optional[str]:
    raw = str(text or "").strip()
    if raw in _EVENT_IDS:
        return raw
    key = _norm(raw)
    if key in _EVENT_TITLE_KEYS:
        return _EVENT_TITLE_KEYS[key]
    compact = key.replace(" ", "_")
    for cid in _EVENT_IDS:
        if compact == cid or compact == cid.replace("menu_", ""):
            return cid
    return None


def _parse_event_topic(text: str) -> Optional[tuple[str, str]]:
    """Parse ``st_{event}_{topic}`` row ids."""
    raw = str(text or "").strip().lower()
    m = re.match(r"^st[_:](.+)$", raw)
    if not m:
        return None
    rest = m.group(1)
    for topic in _TOPIC_BY_KEY:
        suffix = f"_{topic}"
        if rest.endswith(suffix):
            event_slug = rest[: -len(suffix)]
            if event_slug in _EVENT_BY_SLUG:
                return event_slug, topic
    return None


def _parse_event_topic_title(text: str, event_slug: str) -> Optional[tuple[str, str]]:
    """Resolve a list row's visible title when the provider omits its row ID."""
    if event_slug not in _EVENT_BY_SLUG:
        return None
    title = _norm(text)
    for topic in EVENT_TOPICS:
        if event_slug == "rath_yatra" and topic["key"] == "bathing":
            continue
        if title == _norm(topic["title"]):
            return event_slug, str(topic["key"])
    return None


def _parse_sea(text: str) -> Optional[tuple[str, str]]:
    """Parse ``sea_{event}_event_{action}`` → (event_slug, action)."""
    raw = str(text or "").strip().lower()
    m = re.match(r"^sea[_:](.+)$", raw)
    if not m:
        return None
    rest = m.group(1)
    for act in EMERGENCY_ACTIONS:
        suffix = f"_event_{act['key']}"
        if rest.endswith(suffix):
            event_slug = rest[: -len(suffix)]
            if event_slug in _EVENT_BY_SLUG:
                return event_slug, act["key"]
        # legacy place-based ids still accepted
        suffix2 = f"_{act['key']}"
        if rest.endswith(suffix2):
            mid = rest[: -len(suffix2)]
            for slug in _EVENT_BY_SLUG:
                if mid.startswith(f"{slug}_"):
                    return slug, act["key"]
    return None


def _topic_answer(event_slug: str, topic_key: str) -> str:
    topic = _TOPIC_BY_KEY[topic_key]
    answers = topic.get("answers") or {}
    return str(
        answers.get(event_slug)
        or answers.get("kumbh")
        or f"*{topic['title']}* for this event will appear here soon."
    )


async def handle_spiritual_menu_action(
    wa_id: str,
    message: str,
    *,
    tenant_id: str | None = None,
) -> Optional[dict]:
    """Handle spiritual event → platform component / emergency taps."""
    if not is_spiritual_tenant(tenant_id):
        return None

    text = str(message or "").strip()
    if not text:
        return None

    pending_now = _get_pending(wa_id, tenant_id=tenant_id)
    if (
        str(pending_now.get("kind") or "") == "await_location"
        and not _match_event(text)
        and not _parse_event_topic(text)
        and not _parse_sea(text)
        and text not in {"main_menu", "spiritual_main"}
    ):
        await _sender().send_button_message(
            wa_id,
            (
                "Please share your *WhatsApp location* (📎 → Location) "
                "so I can send the nearest help pin.\n\n"
                "If urgent, call local emergency services first."
            ),
            [{"id": "main_menu", "title": "Main Menu"}],
            tenant_id=tenant_id,
        )
        return {"handled": True, "action": "spiritual_await_location_reminder"}

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

    event_id = _match_event(text)
    if event_id:
        await _send_event_topics(wa_id, event_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_event_topics", "category": event_id}

    parsed = _parse_event_topic(text)
    if not parsed:
        parsed = _parse_event_topic_title(
            text, _get_active_event(wa_id, tenant_id=tenant_id),
        )
    if parsed:
        event_slug, topic = parsed
        # Ignore old/stale Rath Yatra bathing menu IDs as well as omitting the
        # option from the current menu.
        if event_slug == "rath_yatra" and topic == "bathing":
            await _send_event_topics(wa_id, "menu_rath_yatra", tenant_id=tenant_id)
            return {"handled": True, "action": "spiritual_event_topics", "category": "menu_rath_yatra"}
        if topic == "emergency":
            await _send_emergency_menu(wa_id, event_slug, tenant_id=tenant_id)
            return {"handled": True, "action": "spiritual_emergency_menu"}
        answer = _topic_answer(event_slug, topic)
        await _sender().send_button_message(
            wa_id,
            answer,
            _event_followup_buttons(event_slug),
            tenant_id=tenant_id,
        )
        return {
            "handled": True,
            "action": "spiritual_event_topic",
            "event": event_slug,
            "topic": topic,
        }

    sea = _parse_sea(text)
    if sea:
        event_slug, action = sea
        category_map = {
            "medical": "medical",
            "police": "police",
            "ambulance": "ambulance",
            "women": "women",
            "sharearea": "any",
        }
        category = category_map.get(action)
        if category:
            await _ask_share_whatsapp_location(
                wa_id,
                tenant_id=tenant_id,
                event_slug=event_slug,
                category=category,
            )
            return {"handled": True, "action": f"spiritual_ask_location_{action}"}

    return None
