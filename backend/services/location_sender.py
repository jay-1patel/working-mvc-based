"""Send tenant brand location pins via Send2 WhatsApp location attachment API."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("services.location_sender")

# Menu / intent ids that should trigger a location pin when brand coords exist
# (or at least the Send2 location endpoint with the directions message).
_LOCATION_TRIGGERS = frozenset({
    "menu_how_to_reach",
    "how_to_reach",
    "how to reach",
    "menu_location",
    "location",
    "directions",
    "reach us",
    "address",
})


def is_location_trigger(text: str | None) -> bool:
    raw = str(text or "").strip().lower()
    if not raw:
        return False
    cleaned = re.sub(r"[\W_]+", " ", raw).strip()
    compact = cleaned.replace(" ", "_")
    if raw in _LOCATION_TRIGGERS or cleaned in _LOCATION_TRIGGERS or compact in _LOCATION_TRIGGERS:
        return True
    return "how to reach" in cleaned or cleaned in {"reach", "directions", "map", "maps"}


def brand_location_payload(tenant_id: str | None = None, wa_id: str = "") -> dict:
    """Read optional brand location fields for the effective tenant."""
    try:
        from shared.tenancy.loader import get_tenant_profile
        from shared.tenancy.resolver import resolve_effective_tenant_id

        tid = resolve_effective_tenant_id(wa_id or "", tenant_id, allow_test_override=True)
        profile = get_tenant_profile(tid or tenant_id)
        brand = profile.brand
        return {
            "tenant_id": profile.tenant_id,
            "name": (getattr(brand, "location_name", None) or brand.display_name() or "").strip(),
            "address": (getattr(brand, "location_address", None) or "").strip(),
            "latitude": getattr(brand, "latitude", None),
            "longitude": getattr(brand, "longitude", None),
            "message": _default_location_message(brand),
        }
    except Exception as exc:
        logger.debug("brand_location_payload unavailable: %s", exc)
        return {}


def _default_location_message(brand) -> str:
    name = (getattr(brand, "location_name", None) or brand.display_name() or "Our location").strip()
    address = (getattr(brand, "location_address", None) or "").strip()
    phone = (getattr(brand, "support_phone", None) or "").strip()
    parts = [f"📍 *{name}*"]
    if address:
        parts.append(address)
    if phone:
        parts.append(f"📞 {phone}")
    parts.append("Open the location pin for directions.")
    return "\n".join(parts)


async def maybe_send_location(
    wa_id: str,
    trigger: str | None,
    *,
    tenant_id: str | None = None,
    message: str | None = None,
) -> bool:
    """If ``trigger`` is a how-to-reach / location action, send the location pin."""
    if not is_location_trigger(trigger):
        return False
    meta = brand_location_payload(tenant_id=tenant_id, wa_id=wa_id)
    try:
        from services.whatsapp_sender import send_location_message
    except ImportError:
        from backend.services.whatsapp_sender import send_location_message

    text = (message or meta.get("message") or "Here is our location.").strip()
    return await send_location_message(
        wa_id,
        text,
        tenant_id=meta.get("tenant_id") or tenant_id,
        latitude=meta.get("latitude"),
        longitude=meta.get("longitude"),
        name=meta.get("name") or None,
        address=meta.get("address") or None,
    )
