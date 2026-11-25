"""Hierarchical WhatsApp menus for the spiritual tenant (PDF-aligned).

Main: Gangasagar · Kumbh Mela · Rath Yatra
Event → Places → Details
  History · Darshan · Reach · Stay · Prasad · Parking · Contact ·
  Emergency · Lost Found

Emergency / Lost Found open action lists and can send location pins.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("services.spiritual_menu_flow")


def _norm(text: str) -> str:
    cleaned = re.sub(r"[\W_]+", " ", str(text or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


# ── Standard place details (answered as text) ────────────────────────────────

DETAIL_TOPICS: list[dict[str, str]] = [
    {
        "key": "history",
        "title": "History",
        "description": "Sacred history & significance",
        "answer": (
            "📜 *History — {place}*\n\n"
            "Sacred history and religious significance of *{place}* "
            "({event}) will be shared from verified sources.\n\n"
            "Ask if you want mythology, architecture, or festival heritage."
        ),
    },
    {
        "key": "darshan",
        "title": "Darshan",
        "description": "Darshan & timings",
        "answer": (
            "🙏 *Darshan / Timings — {place}*\n\n"
            "Darshan windows, opening hours and peak crowd guidance for "
            "*{place}* will appear here from the official schedule.\n\n"
            "Ask for today's morning or evening slot."
        ),
    },
    {
        "key": "reach",
        "title": "Reach",
        "description": "How to reach",
        "answer": (
            "🗺️ *How to Reach — {place}*\n\n"
            "Directions to *{place}* for {event}: nearest rail/road/ferry "
            "and local transport tips.\n\n"
            "Tell us your starting city for a step-by-step plan."
        ),
    },
    {
        "key": "stay",
        "title": "Stay",
        "description": "Where to stay nearby",
        "answer": (
            "🛏️ *Stay near {place}*\n\n"
            "Dharamshalas, ashrams, guest houses and hotels near *{place}* "
            "({event}) will be listed from approved directories.\n\n"
            "Ask for budget, family or senior-friendly options."
        ),
    },
    {
        "key": "prasad",
        "title": "Prasad",
        "description": "Prasad & food nearby",
        "answer": (
            "🍲 *Prasad / Food — {place}*\n\n"
            "Prasad distribution, annadan / bhandara and nearby food points "
            "around *{place}* will be shared here.\n\n"
            "Ask for today's prasad timing if needed."
        ),
    },
    {
        "key": "parking",
        "title": "Parking",
        "description": "Parking & vehicles",
        "answer": (
            "🚗 *Parking — {place}*\n\n"
            "Car, two-wheeler and bus parking near *{place}* "
            "({event}), plus peak-hour tips.\n\n"
            "Ask which vehicle type you are bringing."
        ),
    },
    {
        "key": "contact",
        "title": "Contact",
        "description": "Helpdesk & contacts",
        "answer": (
            "📞 *Contact — {place}*\n\n"
            "Authorised helpdesk / temple contacts for *{place}* "
            "({event}) will appear here once organisers publish them.\n\n"
            "For emergencies, call local emergency services first."
        ),
    },
    # Special: open nested menus (not plain answers)
    {
        "key": "emergency",
        "title": "Emergency",
        "description": "Medical, police, ambulance help",
        "answer": "",
    },
    {
        "key": "lostfound",
        "title": "Lost Found",
        "description": "Missing person / lost item help",
        "answer": "",
    },
]

# Placeholder official pins per event (replace with organiser-verified coords).
# Approximate public reference points — not a substitute for live emergency services.
EVENT_HELP_PINS: dict[str, dict[str, dict[str, Any]]] = {
    "gangasagar": {
        "medical": {
            "name": "Gangasagar Medical Camp",
            "address": "Near Kapil Muni Temple, Gangasagar",
            "latitude": 21.6525,
            "longitude": 88.0752,
            "message": (
                "🚨 *Nearest Medical Camp — Gangasagar*\n\n"
                "If this is life-threatening, call emergency services first.\n"
                "Location pin for the medical camp area is shared above."
            ),
        },
        "police": {
            "name": "Gangasagar Mela Control / Police",
            "address": "Mela control room, Gangasagar",
            "latitude": 21.6530,
            "longitude": 88.0760,
            "message": (
                "👮 *Police / Helpdesk — Gangasagar*\n\n"
                "Mela control / police booth pin is shared above.\n"
                "For immediate danger call local police emergency number."
            ),
        },
        "ambulance": {
            "name": "Gangasagar Ambulance Point",
            "address": "Ambulance stand, Gangasagar Mela",
            "latitude": 21.6518,
            "longitude": 88.0745,
            "message": (
                "🚑 *Ambulance Point — Gangasagar*\n\n"
                "Ambulance stand pin is shared above.\n"
                "Call emergency services if someone needs urgent care."
            ),
        },
        "women": {
            "name": "Women & Child Helpdesk",
            "address": "Women/child helpdesk, Gangasagar Mela",
            "latitude": 21.6522,
            "longitude": 88.0758,
            "message": (
                "👩 *Women / Child Helpdesk — Gangasagar*\n\n"
                "Helpdesk pin is shared above. Ask staff for immediate assistance."
            ),
        },
        "reunion": {
            "name": "Lost & Found / Reunion Centre",
            "address": "Family reunion & lost-found centre, Gangasagar",
            "latitude": 21.6528,
            "longitude": 88.0755,
            "message": (
                "🧭 *Reunion / Lost-Found Centre — Gangasagar*\n\n"
                "Official reunion centre pin is shared above."
            ),
        },
        "lost_counter": {
            "name": "Lost & Found Counter",
            "address": "Lost-found counter, Gangasagar Mela",
            "latitude": 21.6528,
            "longitude": 88.0755,
            "message": (
                "🧳 *Lost & Found Counter — Gangasagar*\n\n"
                "Counter pin is shared above. Carry a case description when you visit."
            ),
        },
    },
    "kumbh": {
        "medical": {
            "name": "Kumbh Medical Camp",
            "address": "Mela medical camp near Sangam",
            "latitude": 25.4295,
            "longitude": 81.8848,
            "message": (
                "🚨 *Nearest Medical Camp — Kumbh*\n\n"
                "If life-threatening, call emergency services first.\n"
                "Medical camp pin is shared above."
            ),
        },
        "police": {
            "name": "Kumbh Police / Control Room",
            "address": "Mela police control room",
            "latitude": 25.4300,
            "longitude": 81.8855,
            "message": (
                "👮 *Police / Helpdesk — Kumbh*\n\n"
                "Control room pin is shared above."
            ),
        },
        "ambulance": {
            "name": "Kumbh Ambulance Point",
            "address": "Ambulance stand, Kumbh Mela",
            "latitude": 25.4290,
            "longitude": 81.8840,
            "message": (
                "🚑 *Ambulance Point — Kumbh*\n\n"
                "Ambulance stand pin is shared above."
            ),
        },
        "women": {
            "name": "Women & Child Helpdesk",
            "address": "Women/child helpdesk, Kumbh Mela",
            "latitude": 25.4298,
            "longitude": 81.8852,
            "message": (
                "👩 *Women / Child Helpdesk — Kumbh*\n\n"
                "Helpdesk pin is shared above."
            ),
        },
        "reunion": {
            "name": "Lost & Found / Reunion Centre",
            "address": "Family reunion centre, Kumbh Mela",
            "latitude": 25.4302,
            "longitude": 81.8850,
            "message": (
                "🧭 *Reunion / Lost-Found Centre — Kumbh*\n\n"
                "Official reunion centre pin is shared above."
            ),
        },
        "lost_counter": {
            "name": "Lost & Found Counter",
            "address": "Lost-found counter, Kumbh Mela",
            "latitude": 25.4302,
            "longitude": 81.8850,
            "message": (
                "🧳 *Lost & Found Counter — Kumbh*\n\n"
                "Counter pin is shared above."
            ),
        },
    },
    "rath_yatra": {
        "medical": {
            "name": "Puri Medical / First Aid",
            "address": "Near Jagannath Temple / Bada Danda, Puri",
            "latitude": 19.8047,
            "longitude": 85.8180,
            "message": (
                "🚨 *Nearest Medical Help — Rath Yatra (Puri)*\n\n"
                "If life-threatening, call emergency services first.\n"
                "Medical / first-aid area pin is shared above."
            ),
        },
        "police": {
            "name": "Puri Police / Yatra Helpdesk",
            "address": "Police / yatra helpdesk near Bada Danda, Puri",
            "latitude": 19.8052,
            "longitude": 85.8185,
            "message": (
                "👮 *Police / Helpdesk — Rath Yatra*\n\n"
                "Helpdesk / police point pin is shared above."
            ),
        },
        "ambulance": {
            "name": "Puri Ambulance Point",
            "address": "Ambulance stand near temple approach, Puri",
            "latitude": 19.8040,
            "longitude": 85.8175,
            "message": (
                "🚑 *Ambulance Point — Rath Yatra*\n\n"
                "Ambulance point pin is shared above."
            ),
        },
        "women": {
            "name": "Women & Child Helpdesk",
            "address": "Women/child helpdesk, Puri Rath Yatra",
            "latitude": 19.8049,
            "longitude": 85.8182,
            "message": (
                "👩 *Women / Child Helpdesk — Rath Yatra*\n\n"
                "Helpdesk pin is shared above."
            ),
        },
        "reunion": {
            "name": "Lost & Found / Reunion Centre",
            "address": "Family reunion centre, Puri",
            "latitude": 19.8055,
            "longitude": 85.8190,
            "message": (
                "🧭 *Reunion / Lost-Found Centre — Rath Yatra*\n\n"
                "Official reunion centre pin is shared above."
            ),
        },
        "lost_counter": {
            "name": "Lost & Found Counter",
            "address": "Lost-found counter, Puri",
            "latitude": 19.8055,
            "longitude": 85.8190,
            "message": (
                "🧳 *Lost & Found Counter — Rath Yatra*\n\n"
                "Counter pin is shared above."
            ),
        },
    },
}

EMERGENCY_ACTIONS: list[dict[str, str]] = [
    {"key": "medical", "title": "Medical Camp", "description": "Nearest medical camp pin"},
    {"key": "police", "title": "Police Desk", "description": "Police / mela control pin"},
    {"key": "ambulance", "title": "Ambulance", "description": "Ambulance stand pin"},
    {"key": "women", "title": "Women Child", "description": "Women & child helpdesk pin"},
    {"key": "sharearea", "title": "Share My Area", "description": "Tell your ghat / area"},
]

LOSTFOUND_ACTIONS: list[dict[str, str]] = [
    {"key": "missing", "title": "Missing Person", "description": "Report someone missing"},
    {"key": "lostitem", "title": "Lost Item", "description": "Report a lost item"},
    {"key": "found", "title": "Report Found", "description": "Report a found person/item"},
    {"key": "reunion", "title": "Reunion Point", "description": "Official reunion centre pin"},
]

# ── Events + places ──────────────────────────────────────────────────────────

EVENTS: dict[str, dict[str, Any]] = {
    "menu_gangasagar": {
        "slug": "gangasagar",
        "title": "Gangasagar",
        "header": "Gangasagar Mela",
        "body": "Choose a place at Gangasagar Mela:",
        "event_label": "Gangasagar Mela",
        "places": [
            {"slug": "kapil_muni", "title": "Kapil Muni", "place": "Kapil Muni Temple"},
            {"slug": "snan_ghat", "title": "Snan Ghat", "place": "Main Snan Ghat"},
            {"slug": "jetty", "title": "Ferry Jetty", "place": "Kachuberia / Jetty"},
            {"slug": "ashram", "title": "Ashrams", "place": "Ashram area"},
            {"slug": "helipad", "title": "Helipad Area", "place": "Helipad / approach"},
            {"slug": "market", "title": "Mela Market", "place": "Mela market & stalls"},
            {"slug": "medical_camp", "title": "Medical Camp", "place": "Medical camp zone"},
        ],
    },
    "menu_kumbh": {
        "slug": "kumbh",
        "title": "Kumbh Mela",
        "header": "Kumbh Mela",
        "body": "Choose a Kumbh place / city:",
        "event_label": "Kumbh Mela",
        "places": [
            {"slug": "prayagraj", "title": "Prayagraj", "place": "Triveni Sangam, Prayagraj"},
            {"slug": "haridwar", "title": "Haridwar", "place": "Har Ki Pauri, Haridwar"},
            {"slug": "nashik", "title": "Nashik", "place": "Ramkund, Nashik"},
            {"slug": "ujjain", "title": "Ujjain", "place": "Shipra Ghat, Ujjain"},
            {"slug": "sangam", "title": "Sangam Ghat", "place": "Sangam bathing ghat"},
            {"slug": "akhara", "title": "Akhara Camp", "place": "Akhara camping area"},
            {"slug": "mela_admin", "title": "Mela Office", "place": "Mela administration"},
        ],
    },
    "menu_rath_yatra": {
        "slug": "rath_yatra",
        "title": "Rath Yatra",
        "header": "Jagannath Rath Yatra",
        "body": "Choose a place for Rath Yatra (Puri):",
        "event_label": "Jagannath Rath Yatra",
        "places": [
            {"slug": "jagannath", "title": "Jagannath", "place": "Jagannath Temple, Puri"},
            {"slug": "gundicha", "title": "Gundicha", "place": "Gundicha Temple"},
            {"slug": "bada_danda", "title": "Bada Danda", "place": "Bada Danda (Grand Road)"},
            {"slug": "railway", "title": "Near Railway", "place": "Puri Railway area"},
            {"slug": "beach", "title": "Sea Beach", "place": "Puri Beach"},
            {"slug": "narendra", "title": "Narendra Tank", "place": "Narendra Tank"},
            {"slug": "singhadwara", "title": "Singha Dwara", "place": "Singha Dwara entrance"},
        ],
    },
}

_TOPIC_BY_KEY = {t["key"]: t for t in DETAIL_TOPICS}
_TEXT_TOPICS = frozenset(t["key"] for t in DETAIL_TOPICS if t["key"] not in {"emergency", "lostfound"})
_EVENT_IDS = frozenset(EVENTS.keys())

_PLACE_BY_ID: dict[str, dict[str, str]] = {}
_PLACE_TITLE_KEYS: dict[str, str] = {}
for _cid, _ev in EVENTS.items():
    for _p in _ev["places"]:
        pid = f"pl_{_ev['slug']}_{_p['slug']}"
        _PLACE_BY_ID[pid] = {
            "id": pid,
            "event_id": _cid,
            "event_slug": str(_ev["slug"]),
            "event_label": str(_ev["event_label"]),
            "place_slug": str(_p["slug"]),
            "title": str(_p["title"]),
            "place": str(_p["place"]),
        }
        tkey = _norm(_p["title"])
        if tkey not in _PLACE_TITLE_KEYS:
            _PLACE_TITLE_KEYS[tkey] = pid

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
        ctx = row.get("context_json") or {}
        if isinstance(ctx, str):
            import json
            ctx = json.loads(ctx or "{}")
        pending = ctx.get("spiritual_pending") or {}
        return pending if isinstance(pending, dict) else {}
    except Exception:
        logger.debug("spiritual_pending load skipped", exc_info=True)
        return {}


def _clear_pending(wa_id: str, *, tenant_id: str | None) -> None:
    _set_pending(wa_id, {}, tenant_id=tenant_id)


async def _send_pin(
    wa_id: str,
    *,
    tenant_id: str | None,
    event_slug: str,
    pin_key: str,
) -> bool:
    pin = (EVENT_HELP_PINS.get(event_slug) or {}).get(pin_key) or {}
    if not pin:
        await _sender().send_button_message(
            wa_id,
            "Location pin will appear once organisers publish verified coordinates.",
            [{"id": "main_menu", "title": "Main Menu"}],
            tenant_id=tenant_id,
        )
        return False
    return await _sender().send_location_message(
        wa_id,
        str(pin.get("message") or "Location pin"),
        tenant_id=tenant_id,
        latitude=pin.get("latitude"),
        longitude=pin.get("longitude"),
        name=pin.get("name"),
        address=pin.get("address"),
    )


async def _send_places(wa_id: str, category_id: str, *, tenant_id: str | None) -> bool:
    meta = EVENTS[category_id]
    rows = []
    for p in meta["places"][:9]:
        rows.append({
            "id": f"pl_{meta['slug']}_{p['slug']}",
            "title": str(p["title"])[:24],
            "description": str(p.get("place") or "")[:72],
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
        "View Places",
        _list_sections(rows, "Places"),
        tenant_id=tenant_id,
    )


async def _send_place_details(
    wa_id: str,
    place_id: str,
    *,
    tenant_id: str | None,
) -> bool:
    place = _PLACE_BY_ID[place_id]
    rows = []
    for topic in DETAIL_TOPICS:
        rows.append({
            "id": f"pd_{place['event_slug']}_{place['place_slug']}_{topic['key']}",
            "title": topic["title"][:24],
            "description": topic["description"][:72],
        })
    # 9 detail rows already = WhatsApp max without a back row
    body = (
        f"*{place['place']}*\n_{place['event_label']}_\n\n"
        "Choose History, Darshan, Reach, Stay, Prasad, Parking, Contact, "
        "Emergency or Lost Found:"
    )
    return await _sender().send_list_menu(
        wa_id,
        str(place["title"])[:60],
        body[:1024],
        "Details",
        _list_sections(rows, "Details"),
        tenant_id=tenant_id,
    )


async def _send_emergency_menu(
    wa_id: str,
    event_slug: str,
    place_slug: str,
    *,
    tenant_id: str | None,
) -> bool:
    place = _PLACE_BY_ID.get(f"pl_{event_slug}_{place_slug}") or {}
    rows = []
    for act in EMERGENCY_ACTIONS:
        rows.append({
            "id": f"sea_{event_slug}_{place_slug}_{act['key']}",
            "title": act["title"][:24],
            "description": act["description"][:72],
        })
    rows.append({
        "id": f"pl_{event_slug}_{place_slug}",
        "title": "Back",
        "description": "Back to place details",
    })
    label = place.get("place") or place_slug
    body = (
        f"🚨 *Emergency — {label}*\n\n"
        "If life-threatening, call local emergency services first.\n"
        "Choose an option for a help pin or guidance:"
    )
    return await _sender().send_list_menu(
        wa_id,
        "Emergency",
        body[:1024],
        "Options",
        _list_sections(rows, "Emergency"),
        tenant_id=tenant_id,
    )


async def _send_lostfound_menu(
    wa_id: str,
    event_slug: str,
    place_slug: str,
    *,
    tenant_id: str | None,
) -> bool:
    place = _PLACE_BY_ID.get(f"pl_{event_slug}_{place_slug}") or {}
    rows = []
    for act in LOSTFOUND_ACTIONS:
        rows.append({
            "id": f"slf_{event_slug}_{place_slug}_{act['key']}",
            "title": act["title"][:24],
            "description": act["description"][:72],
        })
    rows.append({
        "id": f"pl_{event_slug}_{place_slug}",
        "title": "Back",
        "description": "Back to place details",
    })
    label = place.get("place") or place_slug
    body = (
        f"🧭 *Lost & Found — {label}*\n\n"
        "Choose an option. Sensitive cases are handled by authorised helpdesk staff."
    )
    return await _sender().send_list_menu(
        wa_id,
        "Lost Found",
        body[:1024],
        "Options",
        _list_sections(rows, "Lost Found"),
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


def _match_place(text: str) -> Optional[str]:
    raw = str(text or "").strip()
    if raw in _PLACE_BY_ID:
        return raw
    lowered = raw.lower()
    if lowered in _PLACE_BY_ID:
        return lowered
    m = re.match(r"^pl[_:]([a-z0-9_]+)$", raw, re.I)
    if m:
        pid = f"pl_{m.group(1).lower()}"
        if pid in _PLACE_BY_ID:
            return pid
    return _PLACE_TITLE_KEYS.get(_norm(raw))


def _parse_detail(text: str) -> Optional[tuple[str, str, str]]:
    raw = str(text or "").strip()
    m = re.match(r"^pd[_:](.+)$", raw, re.I)
    if not m:
        return None
    rest = m.group(1).lower()
    for topic in _TOPIC_BY_KEY:
        suffix = f"_{topic}"
        if rest.endswith(suffix):
            mid = rest[: -len(suffix)]
            for place in _PLACE_BY_ID.values():
                if mid == f"{place['event_slug']}_{place['place_slug']}":
                    return place["event_slug"], place["place_slug"], topic
    return None


def _parse_sea(text: str) -> Optional[tuple[str, str, str]]:
    raw = str(text or "").strip().lower()
    m = re.match(r"^sea[_:](.+)$", raw)
    if not m:
        return None
    rest = m.group(1)
    for act in EMERGENCY_ACTIONS:
        suffix = f"_{act['key']}"
        if rest.endswith(suffix):
            mid = rest[: -len(suffix)]
            for place in _PLACE_BY_ID.values():
                if mid == f"{place['event_slug']}_{place['place_slug']}":
                    return place["event_slug"], place["place_slug"], act["key"]
    return None


def _parse_slf(text: str) -> Optional[tuple[str, str, str]]:
    raw = str(text or "").strip().lower()
    m = re.match(r"^slf[_:](.+)$", raw)
    if not m:
        return None
    rest = m.group(1)
    for act in LOSTFOUND_ACTIONS:
        suffix = f"_{act['key']}"
        if rest.endswith(suffix):
            mid = rest[: -len(suffix)]
            for place in _PLACE_BY_ID.values():
                if mid == f"{place['event_slug']}_{place['place_slug']}":
                    return place["event_slug"], place["place_slug"], act["key"]
    return None


def _detail_answer(event_slug: str, place_slug: str, topic: str) -> str:
    place_id = f"pl_{event_slug}_{place_slug}"
    place = _PLACE_BY_ID.get(place_id) or {
        "place": place_slug.replace("_", " ").title(),
        "event_label": event_slug.replace("_", " ").title(),
    }
    spec = _TOPIC_BY_KEY[topic]
    return spec["answer"].format(
        place=place["place"],
        event=place["event_label"],
    )


def _followup_buttons(event_slug: str, place_slug: str) -> list[dict]:
    return [
        {"id": f"pd_{event_slug}_{place_slug}_emergency", "title": "Emergency"},
        {"id": f"pd_{event_slug}_{place_slug}_lostfound", "title": "Lost Found"},
        {"id": "main_menu", "title": "Main Menu"},
    ]


async def _handle_pending_reply(
    wa_id: str,
    text: str,
    *,
    tenant_id: str | None,
) -> Optional[dict]:
    pending = _get_pending(wa_id, tenant_id=tenant_id)
    kind = str(pending.get("kind") or "")
    if not kind:
        return None
    # Ignore if user tapped another known control
    if (
        _match_event(text)
        or _match_place(text)
        or _parse_detail(text)
        or _parse_sea(text)
        or _parse_slf(text)
        or text in {"main_menu", "spiritual_main"}
    ):
        return None

    event_slug = str(pending.get("event_slug") or "")
    place_slug = str(pending.get("place_slug") or "")
    place = _PLACE_BY_ID.get(f"pl_{event_slug}_{place_slug}") or {}
    place_label = place.get("place") or place_slug
    event_label = place.get("event_label") or event_slug
    area = text.strip()

    if kind == "share_area":
        _clear_pending(wa_id, tenant_id=tenant_id)
        msg = (
            f"📍 Thanks. You are near *{area}* ({place_label}, {event_label}).\n\n"
            "Sharing the nearest helpdesk / medical pin for this event.\n"
            "If urgent, call local emergency services first."
        )
        await _sender().send_button_message(
            wa_id, msg, _followup_buttons(event_slug, place_slug), tenant_id=tenant_id,
        )
        await _send_pin(wa_id, tenant_id=tenant_id, event_slug=event_slug, pin_key="medical")
        return {"handled": True, "action": "spiritual_share_area", "area": area}

    if kind in {"missing", "lostitem", "found"}:
        _clear_pending(wa_id, tenant_id=tenant_id)
        case_type = {
            "missing": "Missing person",
            "lostitem": "Lost item",
            "found": "Found report",
        }[kind]
        msg = (
            f"🧭 *{case_type} noted*\n\n"
            f"Last place / details: *{area}*\n"
            f"Context: {place_label} ({event_label})\n\n"
            "A case reference will be generated when connected to the official "
            "helpdesk. Sharing the reunion / lost-found centre pin now."
        )
        await _sender().send_button_message(
            wa_id, msg, _followup_buttons(event_slug, place_slug), tenant_id=tenant_id,
        )
        pin_key = "reunion" if kind == "missing" else "lost_counter"
        await _send_pin(wa_id, tenant_id=tenant_id, event_slug=event_slug, pin_key=pin_key)
        return {"handled": True, "action": f"spiritual_{kind}", "details": area}

    return None


async def handle_spiritual_menu_action(
    wa_id: str,
    message: str,
    *,
    tenant_id: str | None = None,
) -> Optional[dict]:
    """Handle spiritual event → place → detail / emergency / lost-found taps."""
    if not is_spiritual_tenant(tenant_id):
        return None

    text = str(message or "").strip()
    if not text:
        return None

    pending_result = await _handle_pending_reply(wa_id, text, tenant_id=tenant_id)
    if pending_result:
        return pending_result

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
        await _send_places(wa_id, event_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_event_places", "category": event_id}

    place_id = _match_place(text)
    if place_id:
        await _send_place_details(wa_id, place_id, tenant_id=tenant_id)
        return {"handled": True, "action": "spiritual_place", "place_id": place_id}

    parsed = _parse_detail(text)
    if parsed:
        event_slug, place_slug, topic = parsed
        if topic == "emergency":
            await _send_emergency_menu(
                wa_id, event_slug, place_slug, tenant_id=tenant_id,
            )
            return {"handled": True, "action": "spiritual_emergency_menu"}
        if topic == "lostfound":
            await _send_lostfound_menu(
                wa_id, event_slug, place_slug, tenant_id=tenant_id,
            )
            return {"handled": True, "action": "spiritual_lostfound_menu"}
        if topic in _TEXT_TOPICS:
            answer = _detail_answer(event_slug, place_slug, topic)
            await _sender().send_button_message(
                wa_id,
                answer,
                _followup_buttons(event_slug, place_slug),
                tenant_id=tenant_id,
            )
            return {
                "handled": True,
                "action": "spiritual_place_detail",
                "event": event_slug,
                "place": place_slug,
                "topic": topic,
            }

    sea = _parse_sea(text)
    if sea:
        event_slug, place_slug, action = sea
        if action == "sharearea":
            _set_pending(
                wa_id,
                {
                    "kind": "share_area",
                    "event_slug": event_slug,
                    "place_slug": place_slug,
                },
                tenant_id=tenant_id,
            )
            await _sender().send_button_message(
                wa_id,
                (
                    "📍 *Share My Area*\n\n"
                    "Type your current ghat / area / landmark "
                    "(example: *Kapil Muni gate* or *Bada Danda north*).\n\n"
                    "I will send the nearest help pin for this event."
                ),
                [{"id": "main_menu", "title": "Main Menu"}],
                tenant_id=tenant_id,
            )
            return {"handled": True, "action": "spiritual_share_area_prompt"}
        pin_map = {
            "medical": "medical",
            "police": "police",
            "ambulance": "ambulance",
            "women": "women",
        }
        pin_key = pin_map.get(action)
        if pin_key:
            await _send_pin(
                wa_id, tenant_id=tenant_id, event_slug=event_slug, pin_key=pin_key,
            )
            await _sender().send_button_message(
                wa_id,
                "Need anything else?",
                _followup_buttons(event_slug, place_slug),
                tenant_id=tenant_id,
            )
            return {"handled": True, "action": f"spiritual_emergency_{action}"}

    slf = _parse_slf(text)
    if slf:
        event_slug, place_slug, action = slf
        if action == "reunion":
            await _send_pin(
                wa_id, tenant_id=tenant_id, event_slug=event_slug, pin_key="reunion",
            )
            await _sender().send_button_message(
                wa_id,
                "Need anything else?",
                _followup_buttons(event_slug, place_slug),
                tenant_id=tenant_id,
            )
            return {"handled": True, "action": "spiritual_reunion_pin"}
        prompts = {
            "missing": (
                "🧭 *Missing Person*\n\n"
                "Reply with last-seen place + short description "
                "(name/age/clothes if known).\n"
                "Example: *Last seen near Sangam ghat, red shirt, age 10*"
            ),
            "lostitem": (
                "🧳 *Lost Item*\n\n"
                "Reply with last-seen place + item description.\n"
                "Example: *Black bag near Jagannath temple gate*"
            ),
            "found": (
                "✋ *Report Found*\n\n"
                "Reply with where you found the person/item + short description.\n"
                "Example: *Found child near Bada Danda police booth*"
            ),
        }
        _set_pending(
            wa_id,
            {
                "kind": action,
                "event_slug": event_slug,
                "place_slug": place_slug,
            },
            tenant_id=tenant_id,
        )
        await _sender().send_button_message(
            wa_id,
            prompts[action],
            [{"id": "main_menu", "title": "Main Menu"}],
            tenant_id=tenant_id,
        )
        return {"handled": True, "action": f"spiritual_{action}_prompt"}

    return None
