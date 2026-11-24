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

# Remove generic vertical defaults so only spiritual options appear.
REMOVE_DEFAULTS = [
    {"id": "menu_offerings", "__remove__": True},
    {"id": "menu_faq", "__remove__": True},
    {"id": "menu_callback", "__remove__": True},
    {"id": "menu_complaint", "__remove__": True},
    {"id": "menu_human", "__remove__": True},
]

SPIRITUAL_BUTTONS = [
    {
        "id": "menu_prasad",
        "title": "Prasad",
        "description": "Prasad offerings & timings",
        "section": "Temple",
        "icon": "🛕",
        "sort_order": 0,
        "enabled": True,
        "intent": "prasad_info",
    },
    {
        "id": "menu_arti_time",
        "title": "Arti Time",
        "description": "Daily arti & aarti schedule",
        "section": "Temple",
        "icon": "🪔",
        "sort_order": 1,
        "enabled": True,
        "intent": "arti_time",
    },
    {
        "id": "menu_how_to_reach",
        "title": "How to Reach",
        "description": "Directions & travel guidance",
        "section": "Visit",
        "icon": "🗺️",
        "sort_order": 2,
        "enabled": True,
        "intent": "how_to_reach",
    },
    {
        "id": "menu_where_to_stay",
        "title": "Where to Stay",
        "description": "Stay options near the temple",
        "section": "Visit",
        "icon": "🛏️",
        "sort_order": 3,
        "enabled": True,
        "intent": "where_to_stay",
    },
    # Drop previous label if it still exists from an older publish.
    {"id": "menu_how_to_stay", "__remove__": True},
    {
        "id": "menu_advantage",
        "title": "Advantage",
        "description": "Benefits of visiting & seva",
        "section": "About",
        "icon": "✨",
        "sort_order": 4,
        "enabled": True,
        "intent": "advantage_info",
    },
    {
        "id": "menu_history",
        "title": "History",
        "description": "Sacred history & heritage",
        "section": "About",
        "icon": "📜",
        "sort_order": 5,
        "enabled": True,
        "intent": "history_info",
    },
    {
        "id": "menu_vehicle_type",
        "title": "Vehicle Type",
        "description": "Parking & vehicle guidance",
        "section": "Visit",
        "icon": "🚗",
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

    intents = list(base.get("intents") or [])
    if not any(isinstance(i, dict) and i.get("name") == "how_to_reach" for i in intents):
        intents.append(
            {
                "name": "how_to_reach",
                "examples": ["how to reach", "directions", "location", "address", "map"],
                "keywords": ["reach", "directions", "location", "address", "map", "route"],
                "answer": (
                    "🗺️ *How to Reach*\n\n"
                    "We have shared the location pin above.\n"
                    "Open it in Maps for turn-by-turn directions.\n"
                    "For help on the way, call our support number."
                ),
            }
        )

    draft = {
        **base,
        "vertical": base.get("vertical") or "generic",
        "display_name": base.get("display_name") or "LEEWAY SOFT TECH PRIVATE LIMITED",
        "brand": brand,
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
