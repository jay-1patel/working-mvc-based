"""Tenant-scoped callback channel selection.

This resolver is deliberately deterministic. AI may provide customer intent,
but it cannot select a channel that the tenant has not enabled or configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from services.token_storage import get_token
from shared.tenancy.loader import get_tenant_profile


@dataclass(frozen=True)
class CallbackDecision:
    mode: str
    booking_url: str = ""
    reason: str = ""


def _valid_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def choose_callback_mode(tenant_id: str, text: str = "") -> CallbackDecision:
    profile = get_tenant_profile(tenant_id)
    policy = profile.callback_policy
    if not profile.features.callback and not profile.features.book_appointment:
        return CallbackDecision("off", reason="callback_feature_disabled")

    instructions = (policy.instructions or "").lower()
    allowed = {str(x).strip().lower() for x in policy.allowed_modes}
    explicit = " ".join((instructions, text or "")).lower()

    if policy.mode == "off" or "callback is disabled" in instructions:
        return CallbackDecision("off", reason="tenant_policy")
    if "phone only" in instructions or "phone callback only" in instructions:
        return CallbackDecision("phone" if "phone" in allowed else "human", reason="explicit_tenant_instruction")
    if policy.mode in allowed and policy.mode != "auto":
        if policy.mode != "booking_url" or _valid_url(policy.booking_url):
            if policy.mode != "google_calendar" or get_token(tenant_id):
                return CallbackDecision(policy.mode, policy.booking_url, "explicit_tenant_policy")

    video_requested = any(term in explicit for term in (
        "video call", "video meeting", "google meet", "meet link", "virtual meeting", "zoom", "teams meeting",
    ))
    if video_requested and "google_calendar" in allowed and get_token(tenant_id):
        return CallbackDecision("google_calendar", reason="explicit_customer_video_request")
    if "booking_url" in allowed and _valid_url(policy.booking_url) and "book online" in explicit:
        return CallbackDecision("booking_url", policy.booking_url, "explicit_customer_booking_request")
    if "phone" in allowed:
        return CallbackDecision("phone", reason="safe_default")
    if "human" in allowed and profile.features.human_handover:
        return CallbackDecision("human", reason="safe_human_fallback")
    return CallbackDecision("off", reason="no_authorized_callback_channel")

