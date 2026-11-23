"""B2B business logic.

Database access uses shared ``database`` / ``db.mongo`` helpers (MongoDB-only).
"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("b2b_tools")


def _repo(name: str):
    from db.mongo import Repository
    return Repository(name)


def _now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# -- Account management (Task 5) -------------------------------------------

def get_distributor_profile(wa_id: str) -> dict:
    """Return the distributor's profile row as a dict (or {} if unknown)."""
    try:
        from db.distributors_ops import get_distributor_by_wa_id
        row = get_distributor_by_wa_id(wa_id)
        if row is None:
            return {}
        d = dict(row)
        raw = d.get("product_interests", "[]")
        if isinstance(raw, str):
            try:
                d["product_interests"] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d["product_interests"] = []
        return d
    except Exception as e:
        logger.error(f"get_distributor_profile failed for {wa_id}: {e}")
        return {}


def get_distributor_tier(wa_id: str) -> str:
    """Return the distributor's tier (default 'Bronze')."""
    profile = get_distributor_profile(wa_id)
    return (profile.get("tier") or "Bronze").strip() or "Bronze"


def get_outstanding_balance(wa_id: str) -> float:
    """Return the distributor's current outstanding payment balance."""
    try:
        profile = get_distributor_profile(wa_id)
        if not profile:
            return 0.0
        return float(profile.get("outstanding_payments") or 0.0)
    except Exception as e:
        logger.error(f"get_outstanding_balance failed for {wa_id}: {e}")
        return 0.0


def get_tier_benefits(tier: str) -> dict:
    """Return the benefits and discount for a given tier.

    Args:
        tier: Tier name (e.g. "Bronze", "Silver", "Gold", "Platinum").

    Returns:
        dict: {"tier", "discount_pct", "benefits": [...]}
    """
    from .config import DIST_TIER_DISCOUNTS, DIST_PRIORITY_TIERS

    tier = (tier or "Bronze").strip().title() or "Bronze"
    discount = float(DIST_TIER_DISCOUNTS.get(tier, 0.0))
    priority = tier in DIST_PRIORITY_TIERS
    benefits = [
        f"{discount * 100:.0f}% discount on bulk orders",
        "Dedicated sales representative",
    ]
    if priority:
        benefits.append("Priority support with fast-tracked tickets")
    else:
        benefits.append("Standard support")
    return {"tier": tier, "discount_pct": discount, "priority": priority, "benefits": benefits}


# -- Product helpers (used by order flow) ----------------------------------

def get_products(category: str = None) -> list:
    """Return active products, optionally filtered by category.

    Prefers the published config snapshot; falls back to the products table.
    """
    try:
        from database import get_published_products
        items = get_published_products(category=category, active_only=True, limit=200)
        return [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "description": p.get("description"),
                "short_description": p.get("short_description"),
                "price": p.get("price"),
                "mrp": p.get("mrp"),
                "unit": p.get("unit"),
                "moq": p.get("moq"),
                "category": p.get("category"),
                "media_url": p.get("media_url"),
                "bulk_discount_tiers": p.get("bulk_discount_tiers", []),
                "nutritional_facts": p.get("nutritional_facts", ""),
                "lead_time_days": p.get("lead_time_days"),
            }
            for p in items
        ]
    except Exception as e:
        logger.error(f"get_products failed: {e}")
        return []


def get_product_by_name(name: str) -> dict:
    """Return a single active product matching a (partial) name, or {}."""
    try:
        from database import get_published_products
        keyword = (name or "").strip().lower()
        items = get_published_products(active_only=True, limit=200)
        for p in items:
            if keyword in (p.get("name") or "").lower():
                return {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "short_description": p.get("short_description"),
                    "price": p.get("price"),
                    "mrp": p.get("mrp"),
                    "unit": p.get("unit"),
                    "moq": p.get("moq"),
                    "category": p.get("category"),
                    "media_url": p.get("media_url"),
                    "bulk_discount_tiers": p.get("bulk_discount_tiers", []),
                    "nutritional_facts": p.get("nutritional_facts", ""),
                "lead_time_days": p.get("lead_time_days"),
                }
        return {}
    except Exception as e:
        logger.error(f"get_product_by_name failed for {name!r}: {e}")
        return {}


def get_product_by_id(product_id) -> dict:
    """Return a single active product by exact id, or {}."""
    try:
        from database import get_published_products
        items = get_published_products(active_only=True, limit=200)
        for p in items:
            if str(p.get("id")) == str(product_id):
                return {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "short_description": p.get("short_description"),
                    "price": p.get("price"),
                    "mrp": p.get("mrp"),
                    "unit": p.get("unit"),
                    "moq": p.get("moq"),
                    "category": p.get("category"),
                    "media_url": p.get("media_url"),
                    "bulk_discount_tiers": p.get("bulk_discount_tiers", []),
                    "nutritional_facts": p.get("nutritional_facts", ""),
                "lead_time_days": p.get("lead_time_days"),
                }
        return {}
    except Exception as e:
        logger.error(f"get_product_by_id failed for {product_id!r}: {e}")
        return {}


def parse_bulk_discount_tiers(raw) -> dict:
    """Parse products.bulk_discount_tiers JSON into {min_qty: discount_pct}.

    Expected shape: [{"min_qty": 100, "discount_pct": 5}, ...]
    """
    if isinstance(raw, dict):
        return {int(k): float(v) for k, v in raw.items()}
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    else:
        data = raw or []
    result = {}
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                qty = entry.get("min_qty") or entry.get("qty")
                pct = entry.get("discount_pct") or entry.get("discount")
                if qty is not None and pct is not None:
                    result[int(qty)] = float(pct)
    elif isinstance(data, dict):
        for k, v in data.items():
            result[int(k)] = float(v)
    return result


def line_item_price(product: dict, qty: int) -> dict:
    """Compute the unit price and total for a product + quantity, applying the
    product's bulk-discount tiers (if any) and the distributor's tier discount.

    Args:
        product: Product dict (with price, bulk_discount_tiers).
        qty: Quantity being ordered.

    Returns:
        dict: {"unit_price", "qty", "line_total", "line_discount", "price_label"}
    """
    list_price = float(product.get("price") or 0.0)

    # Product-level bulk discount based on quantity ordered.
    bulk = parse_bulk_discount_tiers(product.get("bulk_discount_tiers"))
    best_pct = 0.0
    for min_qty, pct in sorted(bulk.items()):
        if qty >= int(min_qty):
            best_pct = max(best_pct, float(pct))
    bulk_discount = list_price * (best_pct / 100.0)
    unit_price = list_price - bulk_discount

    return {
        "unit_price": round(unit_price, 2),
        "qty": int(qty),
        "line_total": round(unit_price * int(qty), 2),
        "line_discount": round(bulk_discount * int(qty), 2),
        "price_label": f"Rs {list_price:.2f}",
    }


def get_moq(product: dict) -> int:
    """Return the product's minimum order quantity (default 1)."""
    try:
        return int(product.get("moq") or 1)
    except (TypeError, ValueError):
        return 1


# -- Order helpers ----------------------------------------------------------

def create_order(wa_id: str, items: list, tier: str = "Bronze",
                 discount_applied: float = 0.0, source: str = "whatsapp") -> str:
    """Create a distributor order via the unified, transactional order service.

    Delegates to backend.services.order_service.create_order() (BEGIN IMMEDIATE
    txn, idempotency, no negative stock). Returns the ORD-XXXXX number.

    Args:
        wa_id: The distributor's WhatsApp ID.
        items: List of line-item dicts with keys name, qty, price (unit price).
        tier: Distributor tier captured at order time.
        discount_applied: Total discount (currency) applied to the order.
        source: Order source (default 'whatsapp').

    Returns:
        str: The generated order number (e.g. ORD-12345).
    """
    from backend.services.order_service import create_order as _unified_create_order, OrderError

    result = _unified_create_order(
        wa_id=wa_id,
        items=items,
        source=f"b2b:{source}",
        idempotency_key=None,  # B2B flow has no checkout session; created once per call
        tier=tier,
        discount_applied=discount_applied,
    )
    logger.info(f"create_order | wa_id={wa_id} | order={result['order_number']} | tier={tier} | duplicate={result.get('duplicate')}")
    return result["order_number"]


def _lead_time(wa_id: str) -> int:
    """Return a lead-time estimate for the distributor's last order (mock)."""
    from .config import DIST_DEFAULT_LEAD_TIME_DAYS
    return DIST_DEFAULT_LEAD_TIME_DAYS


def get_order_status(order_id: str) -> dict:
    """Query the orders table for the status of a given order."""
    try:
        row = _repo("orders").find_one({"order_number": order_id})
        if row is None:
            return {}
        return dict(row)
    except Exception as e:
        logger.error(f"get_order_status failed for {order_id}: {e}")
        return {}


def get_distributor_orders(wa_id: str, limit: int = 10) -> list:
    """Return the distributor's most recent orders."""
    try:
        rows = _repo("orders").find(
            {"wa_id": wa_id},
            sort=[("id", -1)],
            limit=limit,
        )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_distributor_orders failed for {wa_id}: {e}")
        return []


# -- Ticket helpers ---------------------------------------------------------

def create_ticket(wa_id: str, category: str, subject: str, details: str,
                  priority: str = "normal", assigned_to: str = None) -> str:
    """Insert a support ticket into the complaints table and return TICK-XXXXX.

    Args:
        wa_id: The distributor's WhatsApp ID.
        category: Complaint category (stored in complaint_type).
        subject: Short subject line.
        details: Full description.
        priority: Ticket priority (normal / high / urgent).
        assigned_to: Assignee (optional).

    Returns:
        str: The generated ticket number (e.g. TICK-12345).
    """
    seq = (abs(hash(wa_id + category)) % 90000) + 10000
    ticket_id = f"TICK-{seq}"
    now = _now_str()

    _repo("complaints").insert({
        "ticket_id": ticket_id,
        "wa_id": wa_id,
        "complaint_type": category or "Other",
        "description": details or "",
        "status": "open",
        "priority": priority or "normal",
        "assigned_to": assigned_to,
        "subject": subject or category,
        "updated_at": now,
        "created_at": now,
    })
    logger.info(f"create_ticket | wa_id={wa_id} | ticket={ticket_id} | cat={category} | pri={priority}")
    return ticket_id


# -- Existing helpers retained ---------------------------------------------

def get_assigned_sales_rep(wa_id: str) -> dict:
    """Return the distributor's assigned sales representative (mock lookup)."""
    from .config import B2B_DEFAULT_SALES_REP
    return dict(B2B_DEFAULT_SALES_REP)


# -- Price list / schemes / payments / invoices (Distributor Chatbot spec) ---

def get_latest_price_list(category: str = None) -> list:
    """Return the current price-list rows joined with product info.

    Each row: {product_id, name, category, unit, list_price, effective_from,
               effective_to, notes}. Falls back to ``products.price`` when no
    override exists in ``latest_price_list``.
    """
    try:
        from database import list_products

        products = list_products(category=category, active_only=True, limit=500)
        price_overrides = {
            int(r["product_id"]): r
            for r in _repo("latest_price_list").find_all({}, limit=None)
            if r.get("product_id") is not None
        }
        now = datetime.utcnow().date()
        rows = []
        for p in products:
            pid = int(p.get("id") or 0)
            price = p.get("price")
            lpl = price_overrides.get(pid)
            if lpl:
                eff_to = lpl.get("effective_to")
                eff_from = lpl.get("effective_from")
                if eff_to and str(eff_to)[:10] < str(now):
                    lpl = None
                elif eff_from and str(eff_from)[:10] > str(now):
                    lpl = None
                if lpl and lpl.get("price") is not None:
                    price = lpl.get("price")
            rows.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "unit": p.get("unit"),
                "price": price,
                "effective_from": (lpl or {}).get("effective_from"),
                "effective_to": (lpl or {}).get("effective_to"),
                "notes": (lpl or {}).get("notes"),
            })
        return rows
    except Exception as e:
        logger.error(f"get_latest_price_list failed: {e}")
        return []


def get_active_schemes() -> list:
    """Return currently active schemes/offers (within valid_from..valid_to)."""
    try:
        today = datetime.utcnow().date()
        schemes = []
        for row in _repo("schemes_offers").find_all({"active": {"$in": [1, True]}}, limit=None):
            vf = row.get("valid_from")
            vt = row.get("valid_to")
            if vf and str(vf)[:10] > str(today):
                continue
            if vt and str(vt)[:10] < str(today):
                continue
            schemes.append(dict(row))
        schemes.sort(key=lambda r: int(r.get("id") or 0), reverse=True)
        return schemes
    except Exception as e:
        logger.error(f"get_active_schemes failed: {e}")
        return []


def record_payment_confirmation(
    wa_id: str,
    amount: float,
    utr_txn_id: str,
    order_number: str = None,
    notes: str = "",
) -> int:
    """Persist a payment-confirmation request. Returns the new row id."""
    try:
        # Tenancy: resolve from user_states (stamped by the webhook for this
        # conversation) so payment rows land in the right tenant console.
        try:
            from shared.tenancy.resolver import resolve_tenant_for_user
            tenant = resolve_tenant_for_user(wa_id)
        except Exception:
            tenant = None
        row = _repo("payment_confirmations").insert({
            "wa_id": wa_id,
            "amount": float(amount or 0),
            "utr_txn_id": utr_txn_id or "",
            "order_number": order_number or "",
            "notes": notes or "",
            "tenant_id": tenant,
        })
        new_id = row.get("id")
        logger.info(
            f"record_payment_confirmation | wa_id={wa_id} | amount={amount} "
            f"| utr={utr_txn_id} | order={order_number} | id={new_id}"
        )
        return int(new_id or 0)
    except Exception as e:
        logger.error(f"record_payment_confirmation failed: {e}")
        return 0


def record_invoice_request(wa_id: str, order_number: str, notes: str = "") -> int:
    """Persist an invoice request. Returns the new row id.

    Validates that the order exists and belongs to the requesting wa_id.
    Returns 0 if the order is invalid.
    """
    try:
        order = _repo("orders").find_one({"order_number": order_number})
        if order is None:
            logger.info(f"record_invoice_request | unknown order {order_number}")
            return 0
        if order.get("wa_id") and order.get("wa_id") != wa_id:
            logger.info(
                f"record_invoice_request | wa_id mismatch for {order_number} "
                f"(req={wa_id} owner={order.get('wa_id')})"
            )
            return -1  # exists but not theirs
        try:
            from shared.tenancy.resolver import resolve_tenant_for_user
            tenant = resolve_tenant_for_user(wa_id)
        except Exception:
            tenant = None
        row = _repo("invoice_requests").insert({
            "wa_id": wa_id,
            "order_number": order_number,
            "notes": notes or "",
            "tenant_id": tenant,
        })
        new_id = row.get("id")
        logger.info(
            f"record_invoice_request | wa_id={wa_id} | order={order_number} | id={new_id}"
        )
        return int(new_id or 0)
    except Exception as e:
        logger.error(f"record_invoice_request failed: {e}")
        return 0
