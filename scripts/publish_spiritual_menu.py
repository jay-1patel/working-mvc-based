"""Publish spiritual WhatsApp menu with temple/guidance options."""
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

# Remove offerings/FAQ/support leftovers only.
# Do NOT tombstone short ids like "prasad" — merge treats them as clones of
# menu_prasad and would delete the live spiritual rows.
REMOVE_DEFAULTS = [
    {"id": "menu_offerings", "__remove__": True},
    {"id": "browse_offerings", "__remove__": True},
    {"id": "menu_faq", "__remove__": True},
    {"id": "faq_temple", "__remove__": True},
    {"id": "contact_office", "__remove__": True},
    {"id": "menu_callback", "__remove__": True},
    {"id": "menu_complaint", "__remove__": True},
    {"id": "menu_human", "__remove__": True},
]

# Titles stay short (<=10 chars). WhatsApp reply buttons cap at 20 chars;
# list row titles at 24. Do not put emoji in title — it eats the budget.
SPIRITUAL_BUTTONS = [
    {
        "id": "menu_prasad",
        "title": "Prasad",
        "description": "Prasad offerings & timings",
        "section": "Temple",
        "icon": "",
        "sort_order": 0,
        "enabled": True,
        "intent": "prasad_info",
    },
    {
        "id": "menu_arti_time",
        "title": "Arti",
        "description": "Daily arti & aarti schedule",
        "section": "Temple",
        "icon": "",
        "sort_order": 1,
        "enabled": True,
        "intent": "arti_time",
    },
    {
        "id": "menu_how_to_reach",
        "title": "Reach",
        "description": "Directions & travel guidance",
        "section": "Visit",
        "icon": "",
        "sort_order": 2,
        "enabled": True,
        "intent": "how_to_reach",
    },
    {
        "id": "menu_where_to_stay",
        "title": "Stay",
        "description": "Stay options near the temple",
        "section": "Visit",
        "icon": "",
        "sort_order": 3,
        "enabled": True,
        "intent": "where_to_stay",
    },
    {
        "id": "menu_advantage",
        "title": "Benefit",
        "description": "Benefits of visiting & seva",
        "section": "About",
        "icon": "",
        "sort_order": 4,
        "enabled": True,
        "intent": "advantage_info",
    },
    {
        "id": "menu_history",
        "title": "History",
        "description": "Sacred history & heritage",
        "section": "About",
        "icon": "",
        "sort_order": 5,
        "enabled": True,
        "intent": "history_info",
    },
    {
        "id": "menu_vehicle_type",
        "title": "Parking",
        "description": "Parking & vehicle guidance",
        "section": "Visit",
        "icon": "",
        "sort_order": 6,
        "enabled": True,
        "intent": "vehicle_type",
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
    # Location pin fields used by Send2 /whatsapp/attachment/location on How to Reach.
    brand.setdefault("location_name", brand.get("bot_name") or "Aastha")
    brand.setdefault(
        "location_address",
        brand.get("location_address")
        or "LEEWAY SOFT TECH PRIVATE LIMITED — update address in brand profile",
    )
    # Set real temple coordinates when available, e.g. brand["latitude"]=23.02

    # Ensure every spiritual menu intent exists and is enabled, otherwise
    # profile_button_status used to mark the WhatsApp row unavailable.
    intent_defs = {
        "prasad_info": {
            "examples": ["prasad", "prasad timing", "prasad offerings"],
            "keywords": ["prasad", "prasadam", "blessed food"],
            "answer": "🛕 *Prasad*\n\nPrasad details will be shared here. Please ask if you need today's timing.",
        },
        "arti_time": {
            "examples": ["arti time", "aarti timing", "when is arti"],
            "keywords": ["arti", "aarti", "timing", "puja time"],
            "answer": "🪔 *Arti Time*\n\nDaily arti timings will be shared here. Ask for morning or evening schedule.",
        },
        "how_to_reach": {
            "examples": ["how to reach", "directions", "location", "address", "map"],
            "keywords": ["reach", "directions", "location", "address", "map", "route"],
            "answer": (
                "🗺️ *How to Reach*\n\n"
                "We have shared the location pin above.\n"
                "Open it in Maps for turn-by-turn directions.\n"
                "For help on the way, call our support number."
            ),
        },
        "where_to_stay": {
            "examples": ["where to stay", "stay options", "lodging", "dharamshala"],
            "keywords": ["stay", "lodge", "hotel", "dharamshala", "accommodation"],
            "answer": "🛏️ *Where to Stay*\n\nStay options near the temple will be shared here.",
        },
        "advantage_info": {
            "examples": ["advantage", "benefits", "why visit"],
            "keywords": ["advantage", "benefits", "seva", "blessing"],
            "answer": "✨ *Advantage*\n\nBenefits of visiting and seva will be shared here.",
        },
        "history_info": {
            "examples": ["history", "heritage", "origin"],
            "keywords": ["history", "heritage", "origin", "story"],
            "answer": "📜 *History*\n\nSacred history and heritage will be shared here.",
        },
        "vehicle_type": {
            "examples": ["vehicle type", "parking", "car parking"],
            "keywords": ["vehicle", "parking", "car", "bike", "bus"],
            "answer": "🚗 *Vehicle Type*\n\nParking and vehicle guidance will be shared here.",
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
            "body": "Welcome. How may we guide your spiritual journey today?",
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
    for b in profile.menu.buttons:
        print(f"  {b.sort_order}. {b.id} | {b.title} | {b.description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
