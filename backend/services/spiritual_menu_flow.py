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

# Facilities live in Mongo ``event_facilities`` (tenant_id, event, type, name,
# lat/lng, address, message). Seed via scripts/seed_event_facilities.py and
# manage via POST /api/admin/tenants/{tenant_id}/event-facilities/{list|create|update|delete}.

EMERGENCY_ACTIONS: list[dict[str, str]] = [
    {"key": "medical", "title": "Medical Camp", "description": "Share GPS for nearest camp"},
    {"key": "police", "title": "Police Desk", "description": "Share GPS for nearest desk"},
    {"key": "ambulance", "title": "Ambulance", "description": "Share GPS for ambulance"},
    {"key": "women", "title": "Women Child", "description": "Share GPS for helpdesk"},
    {"key": "sharearea", "title": "Share Location", "description": "WhatsApp location → nearest help"},
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
    """Map DB row → pin shape used by send/nearest helpers."""
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
    """Send first matching facility pin (fallback when no user GPS)."""
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
    place_slug: str,
    category: str,
) -> None:
    labels = {
        "medical": "nearest medical camp",
        "police": "nearest police / helpdesk",
        "ambulance": "nearest ambulance point",
        "women": "nearest women & child helpdesk",
        "reunion": "nearest reunion centre",
        "lost_counter": "nearest lost & found counter",
        "any": "nearest emergency help",
    }
    label = labels.get(category, "nearest help point")
    _set_pending(
        wa_id,
        {
            "kind": "await_location",
            "event_slug": event_slug,
            "place_slug": place_slug,
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
    """Handle inbound WhatsApp location share → nearest facility pin."""
    if not is_spiritual_tenant(tenant_id):
        return None
    pending = _get_pending(wa_id, tenant_id=tenant_id)
    if str(pending.get("kind") or "") != "await_location":
        return None

    event_slug = str(pending.get("event_slug") or "")
    place_slug = str(pending.get("place_slug") or "")
    category = str(pending.get("category") or "any")
    if not event_slug:
        return None

    cat = None if category in {"", "any"} else category
    found = find_nearest_facility(
        event_slug, latitude, longitude, category=cat, tenant_id=tenant_id,
    )
    if not found and cat:
        # Fall back to any help point for this event
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
    buttons = (
        _followup_buttons(event_slug, place_slug)
        if place_slug
        else [{"id": "main_menu", "title": "Main Menu"}]
    )
    await _sender().send_button_message(wa_id, preface, buttons, tenant_id=tenant_id)
    return {
        "handled": True,
        "action": "spiritual_nearest_pin",
        "facility": facility.get("name"),
        "km": km,
        "category": facility.get("key"),
    }


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

    # Waiting for WhatsApp location share — remind if user typed instead.
    pending_now = _get_pending(wa_id, tenant_id=tenant_id)
    if (
        str(pending_now.get("kind") or "") == "await_location"
        and not _match_event(text)
        and not _match_place(text)
        and not _parse_detail(text)
        and not _parse_sea(text)
        and not _parse_slf(text)
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
                place_slug=place_slug,
                category=category,
            )
            return {"handled": True, "action": f"spiritual_ask_location_{action}"}

    slf = _parse_slf(text)
    if slf:
        event_slug, place_slug, action = slf
        if action == "reunion":
            await _ask_share_whatsapp_location(
                wa_id,
                tenant_id=tenant_id,
                event_slug=event_slug,
                place_slug=place_slug,
                category="reunion",
            )
            return {"handled": True, "action": "spiritual_ask_location_reunion"}
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
