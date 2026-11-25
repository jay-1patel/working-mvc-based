"""Publish spiritual WhatsApp menu: 3 events → places → details.

Main: Gangasagar, Kumbh Mela, Rath Yatra
Each event opens Places; each place opens
History / Darshan / Reach / Stay / Prasad / Parking / Contact.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

env_path = ROOT / "routing" / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, val = line.partition("=")
    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

os.environ.setdefault("DATABASE_BACKEND", "mongodb")

from shared.tenancy import store as tenancy_store  # noqa: E402
from shared.tenancy.loader import reload_profile  # noqa: E402

TENANT_ID = "spiritual"

REMOVE_DEFAULTS = [
    {"id": "menu_spiritual_guide", "__remove__": True},
    {"id": "menu_emergency", "__remove__": True},
    {"id": "menu_lost_found", "__remove__": True},
    {"id": "menu_seva", "__remove__": True},
    {"id": "menu_north_temples", "__remove__": True},
    {"id": "menu_south_temples", "__remove__": True},
    {"id": "menu_north_yatra", "__remove__": True},
    {"id": "menu_south_yatra", "__remove__": True},
    {"id": "menu_4_dham", "__remove__": True},
    {"id": "menu_gujarat", "__remove__": True},
    {"id": "menu_prasad", "__remove__": True},
    {"id": "menu_arti_time", "__remove__": True},
    {"id": "menu_how_to_reach", "__remove__": True},
    {"id": "menu_where_to_stay", "__remove__": True},
    {"id": "menu_advantage", "__remove__": True},
    {"id": "menu_history", "__remove__": True},
    {"id": "menu_vehicle_type", "__remove__": True},
    {"id": "menu_offerings", "__remove__": True},
    {"id": "browse_offerings", "__remove__": True},
    {"id": "menu_faq", "__remove__": True},
    {"id": "faq_temple", "__remove__": True},
    {"id": "contact_office", "__remove__": True},
    {"id": "menu_callback", "__remove__": True},
    {"id": "menu_complaint", "__remove__": True},
    {"id": "menu_human", "__remove__": True},
]

SPIRITUAL_BUTTONS = [
    {
        "id": "menu_gangasagar",
        "title": "Gangasagar",
        "description": "Places at Gangasagar Mela",
        "section": "Events",
        "icon": "",
        "sort_order": 0,
        "enabled": True,
        "intent": "gangasagar_mela",
    },
    {
        "id": "menu_kumbh",
        "title": "Kumbh Mela",
        "description": "Places at Kumbh Mela",
        "section": "Events",
        "icon": "",
        "sort_order": 1,
        "enabled": True,
        "intent": "kumbh_mela",
    },
    {
        "id": "menu_rath_yatra",
        "title": "Rath Yatra",
        "description": "Places for Jagannath Rath Yatra",
        "section": "Events",
        "icon": "",
        "sort_order": 2,
        "enabled": True,
        "intent": "rath_yatra",
    },
]


def main() -> int:
    base = tenancy_store.get_current_payload(TENANT_ID) or {}
    if not isinstance(base, dict):
        base = {}

    brand = dict(base.get("brand") or {})
    brand.setdefault("bot_name", "Aastha")
    brand.setdefault(
        "signature",
        "May peace and blessings be with you. — Aastha",
    )
    if not str(brand.get("name") or "").strip() or brand.get("name") == "Brand":
        brand["name"] = "Universal Spiritual AI"
    brand["tagline"] = (
        brand.get("tagline")
        or "AI companion for Melas, Yatras and pilgrimage places"
    )
    brand.setdefault("location_name", brand.get("bot_name") or "Aastha")
    brand.setdefault(
        "location_address",
        brand.get("location_address")
        or "Update event venue address in brand profile",
    )

    intent_defs = {
        "gangasagar_mela": {
            "examples": ["gangasagar", "gangasagar mela"],
            "keywords": ["gangasagar", "kapil muni"],
            "answer": "Opening Gangasagar places…",
        },
        "kumbh_mela": {
            "examples": ["kumbh", "kumbh mela"],
            "keywords": ["kumbh", "sangam"],
            "answer": "Opening Kumbh places…",
        },
        "rath_yatra": {
            "examples": ["rath yatra", "jagannath"],
            "keywords": ["rath yatra", "jagannath", "puri"],
            "answer": "Opening Rath Yatra places…",
        },
    }
    intents = list(base.get("intents") or [])
    by_name = {
        str(i.get("name")): i
        for i in intents
        if isinstance(i, dict) and i.get("name")
    }
    for name, spec in intent_defs.items():
        existing = by_name.get(name)
        if existing is None:
            intents.append({"name": name, "enabled": True, **spec})
        else:
            existing["enabled"] = True
            for key, value in spec.items():
                existing.setdefault(key, value)

    vocabulary = dict(base.get("vocabulary") or {})
    vocabulary["browse_label"] = "Options"

    draft = {
        **base,
        "vertical": base.get("vertical") or "generic",
        "display_name": base.get("display_name") or "Universal Spiritual AI",
        "brand": brand,
        "vocabulary": vocabulary,
        "intents": intents,
        "menu": {
            "key": "kb_main",
            "header": brand.get("bot_name") or "Aastha",
            "body": (
                "Namaste. Choose a sacred event to explore places, "
                "darshan, travel and stay:"
            ),
            "footer": "Or type your question directly",
            "button_text": "Show Options",
            "buttons": [*SPIRITUAL_BUTTONS, *REMOVE_DEFAULTS],
        },
    }

    version = tenancy_store.publish_version(
        TENANT_ID,
        draft,
        published_by="spiritual-menu-script",
    )
    profile = reload_profile(TENANT_ID)
    print("published version", version)
    print("visible menu:")
    for b in profile.menu.visible_buttons(profile.features):
        print(f"  {b.sort_order}. {b.id} | {b.title} | {b.description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
