"""Create payment links for WhatsApp checkout (no admin JWT required).

Used by B2C/B2B bots after an order is placed. Reuses the same Stripe /
Razorpay / custom providers as the admin create-session route.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("payment_checkout")


def _use_mongodb():
    from db.core import use_mongodb
    return use_mongodb()


def _load_payment_integration(tenant_id: str, provider: Optional[str]):
    prov = (provider or "").lower().strip()
    if _use_mongodb():
        from db.mongo import Repository
        integrations = Repository("tenant_integrations")
        if not prov:
            rows = integrations.find(
                {
                    "tenant_id": tenant_id,
                    "api_type": "payment_api",
                    "is_active": 1,
                },
                sort=[("status", 1)],
                limit=10,
            )
            verified = [r for r in rows if r.get("status") == "verified"]
            row = verified[0] if verified else (rows[0] if rows else None)
            if not row:
                return None, None, {
                    "ok": False,
                    "skipped": True,
                    "error": "No active payment gateway configured",
                }
            prov = str(row.get("provider") or "")
        else:
            row = integrations.find_one(
                {"tenant_id": tenant_id, "provider": prov, "is_active": 1},
            )
            if not row:
                return None, None, {
                    "ok": False,
                    "error": f"Provider '{prov}' is not configured",
                }
        creds = row.get("credentials_json") or {}
        if isinstance(creds, str):
            creds = json.loads(creds or "{}")
        return prov, creds, None
    raise RuntimeError("payment integration lookup requires MongoDB")


def _persist_payment_row(
    tenant_id: str,
    order_id: str,
    prov: str,
    amount: float,
    currency: str,
    payment_id: str,
    session_id: Optional[str],
    payment_url: str,
    result: Dict[str, Any],
) -> None:
    if _use_mongodb():
        from db.mongo import Repository
        Repository("tenant_payments").insert({
            "tenant_id": tenant_id,
            "order_id": order_id,
            "provider": prov,
            "amount": amount,
            "currency": currency,
            "payment_id": payment_id,
            "session_id": session_id,
            "payment_url": payment_url,
            "status": "created",
            "raw_response": result,
        })
        Repository("orders").update(
            {"order_number": order_id, "tenant_id": tenant_id},
            {"payment_status": "pending", "payment_method": prov},
        )
        return
    raise RuntimeError("payment persistence requires MongoDB")


async def create_payment_link(
    tenant_id: str,
    order_id: str,
    amount: float,
    *,
    currency: str = "INR",
    description: str = "WhatsApp Order Payment",
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a payment URL for an order.

    Returns ``{ok, payment_url, provider, payment_id, ...}`` or
    ``{ok: False, error, skipped?}`` when no gateway is configured.
    """
    if not tenant_id or not order_id or not amount or amount <= 0:
        return {"ok": False, "error": "invalid payment request"}

    try:
        from shared.tenancy import get_profile
        profile = get_profile(tenant_id)
        if profile and not profile.features.is_on("payments"):
            return {
                "ok": False,
                "skipped": True,
                "error": "Payments feature is disabled for this tenant",
            }
    except Exception as feat_err:
        logger.debug("Could not check payments feature for tenant %s: %s", tenant_id, feat_err)

    try:
        from services.integrations import (
            CustomIntegrationService,
            RazorpayService,
            StripeService,
        )
    except Exception as exc:
        logger.error("payment integrations unavailable: %s", exc)
        return {"ok": False, "error": "payment integrations unavailable"}

    prov, creds, early = _load_payment_integration(tenant_id, provider)
    if early:
        return early

    result: Dict[str, Any] = {"ok": False, "error": "Provider not supported"}
    if "stripe" in prov:
        api_key = creds.get("secret_key") or creds.get("api_key") or ""
        result = await StripeService.create_checkout_session(
            api_key=api_key,
            amount=amount,
            currency=currency,
            order_id=order_id,
            description=description,
            customer_email=customer_email,
        )
    elif "razorpay" in prov:
        key_id = creds.get("key_id") or creds.get("api_key") or ""
        key_secret = creds.get("key_secret") or creds.get("secret") or ""
        result = await RazorpayService.create_payment_link(
            key_id=key_id,
            key_secret=key_secret,
            amount=amount,
            currency=currency,
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            description=description,
        )
    elif "custom" in prov:
        endpoint_url = creds.get("endpoint_url") or creds.get("api_url") or ""
        auth_header = creds.get("auth_header") or creds.get("api_key") or ""
        result = await CustomIntegrationService.process_custom_payment(
            endpoint_url=endpoint_url,
            auth_header=auth_header,
            amount=amount,
            currency=currency,
            order_id=order_id,
            customer_phone=customer_phone,
        )

    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "Payment link generation failed"),
            "provider": prov,
        }

    payment_id = (
        result.get("payment_link_id")
        or result.get("session_id")
        or result.get("payment_id")
        or ""
    )
    payment_url = result.get("payment_url") or ""

    try:
        _persist_payment_row(
            tenant_id,
            order_id,
            prov,
            amount,
            currency,
            payment_id,
            result.get("session_id"),
            payment_url,
            result,
        )
    except Exception as exc:
        logger.warning("Could not persist payment row for %s: %s", order_id, exc)

    return {
        "ok": True,
        "provider": prov,
        "order_id": order_id,
        "payment_url": payment_url,
        "payment_id": payment_id,
        "amount": amount,
        "currency": currency,
    }


def mark_order_paid(tenant_id: str, order_id: str, payment_id: str = "") -> bool:
    """Flip order + tenant_payments to paid after a gateway webhook."""
    if not tenant_id or not order_id:
        return False
    try:
        if _use_mongodb():
            from db.mongo import Repository
            orders = Repository("orders")
            payments = Repository("tenant_payments")
            orders.update_many(
                {"order_number": order_id, "tenant_id": tenant_id},
                {"payment_status": "paid"},
            )
            order_row = orders.find_one({"order_number": order_id, "tenant_id": tenant_id})
            if order_row and order_row.get("status") == "placed":
                orders.update(
                    {"order_number": order_id, "tenant_id": tenant_id},
                    {"status": "confirmed"},
                )
            if payment_id:
                payments.update_many(
                    {
                        "tenant_id": tenant_id,
                        "$or": [
                            {"order_id": order_id},
                            {"payment_id": payment_id},
                            {"session_id": payment_id},
                        ],
                    },
                    {"status": "paid"},
                )
            else:
                payments.update_many(
                    {"tenant_id": tenant_id, "order_id": order_id},
                    {"status": "paid"},
                )
            return True
        raise RuntimeError("mark_order_paid requires MongoDB")
    except Exception as exc:
        logger.error("mark_order_paid failed tenant=%s order=%s: %s", tenant_id, order_id, exc)
        return False


def resolve_tenant_id_for_wa(wa_id: str) -> str:
    try:
        from shared.tenancy.resolver import resolve_tenant_for_user
        return resolve_tenant_for_user(wa_id) or ""
    except Exception:
        return ""