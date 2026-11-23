"""Admin API for orders placed through the WhatsApp bot.

Order rows are created by the B2B (``bots/distributor_b2b``) and B2C
(``bots/customer_b2c``) workflows, as well as the KB bot. Agents use these
endpoints to review, filter, update status, and manage orders from the Admin
Panel.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database import (
    delete_order_record,
    get_order_record,
    list_admin_orders,
    order_stats,
    record_admin_audit_event,
    update_order_record,
)
from db.core import use_mongodb
from routes.auth import require_permission
from shared.tenancy.gating import is_enabled

logger = logging.getLogger("orders")
router = APIRouter(prefix="/api/orders")


def _require_orders(current_admin: dict):
    if current_admin.get("role") == "super_admin":
        return current_admin
    tenant_id = current_admin.get("tenant_id")
    if tenant_id and not is_enabled(tenant_id, "orders"):
        raise HTTPException(
            status_code=403,
            detail=f"Orders feature is not enabled for tenant '{tenant_id}'",
        )
    return current_admin

ALLOWED_STATUSES = {
    "placed",
    "confirmed",
    "processing",
    "shipped",
    "delivered",
    "completed",
    "cancelled",
    "returned",
}
ALLOWED_PAYMENT_STATUSES = {"pending", "paid", "failed", "refunded", "cod"}


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None
    delivery_date: Optional[str] = None
    tier: Optional[str] = None
    discount_applied: Optional[float] = None
    total_amount: Optional[float] = None
    notes: Optional[str] = None


@router.get("")
def list_orders(
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    q: str = Query(""),
    limit: int = Query(200, le=500),
    current_admin: dict = Depends(require_permission("view_orders")),
):
    _require_orders(current_admin)
    return list_admin_orders(
        status=status,
        order_type=order_type,
        payment_status=payment_status,
        q=q,
        limit=limit,
    )


@router.get("/stats")
def order_stats_route(current_admin: dict = Depends(require_permission("view_orders"))):
    _require_orders(current_admin)
    return order_stats()


@router.get("/{order_id}")
def get_order(
    order_id: str,
    current_admin: dict = Depends(require_permission("view_orders")),
):
    _require_orders(current_admin)
    row = get_order_record(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order": row}


@router.put("/{order_id}")
def update_order(
    order_id: str,
    body: OrderUpdate,
    current_admin: dict = Depends(require_permission("manage_orders")),
):
    _require_orders(current_admin)
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Nothing to update")

    if body.status is not None and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if body.payment_status is not None and body.payment_status not in ALLOWED_PAYMENT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"payment_status must be one of {sorted(ALLOWED_PAYMENT_STATUSES)}",
        )

    row_id = update_order_record(order_id, payload)
    if row_id is None:
        raise HTTPException(status_code=404, detail="Order not found")

    audit_kwargs = dict(
        action="order_updated",
        actor=current_admin,
        resource_type="order",
        resource_id=row_id,
        details={"order_id": order_id, "updated_fields": list(payload.keys())},
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit_kwargs)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit_kwargs)

    logger.info("ORDER_UPDATED | %s | %s | by %s", order_id, payload, current_admin.get("username"))
    return {"status": "ok", "order_id": order_id, "updated": payload}


@router.delete("/{order_id}")
def delete_order(
    order_id: str,
    current_admin: dict = Depends(require_permission("manage_orders")),
):
    _require_orders(current_admin)
    row = delete_order_record(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    audit_kwargs = dict(
        action="order_deleted",
        actor=current_admin,
        resource_type="order",
        resource_id=row.get("id"),
        details={
            "order_id": order_id,
            "order_number": row.get("order_number") or order_id,
        },
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit_kwargs)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit_kwargs)

    logger.info("ORDER_DELETED | %s | by %s", order_id, current_admin.get("username"))
    return {"status": "ok", "order_id": order_id}