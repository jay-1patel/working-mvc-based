"""Publish spiritual WhatsApp hierarchical menu.

Main:
  North Temples, South Temples, North Yatra, South Yatra, 4 Dham, Gujarat

North/South Temples (and other categories) open a destination list; each
destination opens Prasad / Arti / Reach / Stay / Benefit / History / Parking.
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

# Tombstone old flat spiritual rows + commerce leftovers so they leave the menu.
REMOVE_DEFAULTS = [
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

# Titles stay short (WhatsApp list row title <= 24, reply button <= 20).
SPIRITUAL_BUTTONS = [
    {
        "id": "menu_north_temples",
        "title": "North Temples",
        "description": "7 sacred temples of North India",
        "section": "Temples",
        "icon": "",
        "sort_order": 0,
        "enabled": True,
        "intent": "north_temples",
    },
    {
        "id": "menu_south_temples",
        "title": "South Temples",
        "description": "7 sacred temples of South India",
        "section": "Temples",
        "icon": "",
        "sort_order": 1,
        "enabled": True,
        "intent": "south_temples",
    },
    {
        "id": "menu_north_yatra",
        "title": "North Yatra",
        "description": "North India pilgrimage journeys",
        "section": "Pilgrimage",
        "icon": "",
        "sort_order": 2,
        "enabled": True,
        "intent": "north_pilgrimage",
    },
    {
        "id": "menu_south_yatra",
        "title": "South Yatra",
        "description": "South India pilgrimage journeys",
        "section": "Pilgrimage",
        "icon": "",
        "sort_order": 3,
        "enabled": True,
        "intent": "south_pilgrimage",
    },
    {
        "id": "menu_4_dham",
        "title": "4 Dham",
        "description": "Badrinath, Dwarka, Puri, Rameswaram",
        "section": "Pilgrimage",
        "icon": "",
        "sort_order": 4,
        "enabled": True,
        "intent": "four_dham",
    },
    {
        "id": "menu_gujarat",
        "title": "Gujarat",
        "description": "Famous temples of Gujarat",
        "section": "Temples",
        "icon": "",
        "sort_order": 5,
        "enabled": True,
        "intent": "gujarat_temples",
    },
]


def main() -> int:
    base = tenancy_store.get_current_payload(TENANT_ID) or {}
    if not isinstance(base, dict):
        base = {}

    brand = dict(base.get("brand") or {})
    brand.setdefault("bot_name", "Aastha")
    brand.setdefault("signature", "May peace and blessings be with you. — Aastha")
    if not str(brand.get("name") or "").strip() or brand.get("name") == "Brand":
        brand["name"] = "LEEWAY SOFT TECH PRIVATE LIMITED"
    brand.setdefault("location_name", brand.get("bot_name") or "Aastha")
    brand.setdefault(
        "location_address",
        brand.get("location_address")
        or "LEEWAY SOFT TECH PRIVATE LIMITED — update address in brand profile",
    )

    # Category intents exist so profile_button_status marks rows available.
    # Actual lists are opened by spiritual_menu_flow (not these answers).
    intent_defs = {
        "north_temples": {
            "examples": ["north temples", "temples in north"],
            "keywords": ["north temple", "north temples"],
            "answer": "Northern temples list is opening…",
        },
        "south_temples": {
            "examples": ["south temples", "temples in south"],
            "keywords": ["south temple", "south temples"],
            "answer": "Southern temples list is opening…",
        },
        "north_pilgrimage": {
            "examples": ["north pilgrimage", "north yatra"],
            "keywords": ["north yatra", "north pilgrimage"],
            "answer": "North pilgrimage list is opening…",
        },
        "south_pilgrimage": {
            "examples": ["south pilgrimage", "south yatra"],
            "keywords": ["south yatra", "south pilgrimage"],
            "answer": "South pilgrimage list is opening…",
        },
        "four_dham": {
            "examples": ["4 dham", "char dham", "four dham"],
            "keywords": ["4 dham", "char dham", "four dham"],
            "answer": "Char Dham list is opening…",
        },
        "gujarat_temples": {
            "examples": ["gujarat temples", "famous temples of gujarat"],
            "keywords": ["gujarat", "gujarat temple"],
            "answer": "Famous Gujarat temples list is opening…",
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
        "display_name": base.get("display_name") or "LEEWAY SOFT TECH PRIVATE LIMITED",
        "brand": brand,
        "vocabulary": vocabulary,
        "intents": intents,
        "menu": {
            "key": "kb_main",
            "header": brand.get("bot_name") or "Aastha",
            "body": "Welcome. Choose a sacred path to explore:",
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
