"""Tenant-scoped Customers and Orders APIs for the admin console."""

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from database import record_admin_audit_event
from db.core import use_mongodb
from db.tenant_operations_ops import (
    tenant_delete_order,
    tenant_export_customer_rows,
    tenant_get_order,
    tenant_list_customers,
    tenant_list_orders,
    tenant_order_stats,
    tenant_update_order,
)
from routes.auth import authorize_tenant_access, get_current_admin, has_permission, require_tenant_admin_permission, security, session_tenant_id
from routes.orders import ALLOWED_PAYMENT_STATUSES, ALLOWED_STATUSES, OrderUpdate


logger = logging.getLogger("tenant_operations")
router = APIRouter(prefix="/api/admin/tenants/{tenant_id}", tags=["tenant-operations"])
flat_router = APIRouter(prefix="/api/admin/tenants", tags=["tenant-operations"])


class CustomersListRequest(BaseModel):
    q: str = ""
    limit: int = 200


class CustomersExportRequest(BaseModel):
    format: str = "csv"


def _flat_customer_admin(request: Request, credentials) -> tuple[dict, str]:
    tenant_id = session_tenant_id(request=request)
    principal = authorize_tenant_access(request, tenant_id, credentials)
    if principal.get("type") == "tenant":
        return principal, tenant_id
    admin = get_current_admin(request, credentials)
    if admin.get("role") != "super_admin" and not has_permission(admin, "view_customers"):
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
    return admin, tenant_id


def _record_audit(**kwargs):
    if use_mongodb():
        record_admin_audit_event(None, **kwargs)
    else:
        from database import get_db_context

        with get_db_context() as conn:
            record_admin_audit_event(conn, **kwargs)


@flat_router.post("/customers")
def list_tenant_customers_route(
    body: CustomersListRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Aggregate this tenant's customers without mixing rows for shared WA IDs."""
    q, limit = body.q, body.limit
    _flat_customer_admin(request, credentials)
    tenant_id = session_tenant_id(request=request)
    return tenant_list_customers(tenant_id=tenant_id, q=q, limit=limit)


@flat_router.post("/customers/export")
def export_tenant_customers(
    body: CustomersExportRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """The tenant's customer directory as a downloadable CSV or Excel file."""
    format = body.format
    _flat_customer_admin(request, credentials)
    tenant_id = session_tenant_id(request=request)
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=422, detail="format must be csv or xlsx")
    import csv as csv_mod

    from fastapi.responses import StreamingResponse

    rows = tenant_export_customer_rows(tenant_id)

    headers = [
        "WhatsApp ID", "Name", "Phone", "Email", "City", "State", "Company",
        "Language", "Messages", "First seen", "Last seen",
    ]

    def row_values(r):
        return [
            r["wa_id"], r["name"], r["phone"] or r["wa_id"], r["email"], r["city"], r["state"],
            r["company"], r["language"],
            r["message_count"], r["first_seen"], r["last_seen"],
        ]

    if format == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Customers"
        sheet.append(headers)
        for r in rows:
            sheet.append(row_values(r))
        buf = io.BytesIO()
        workbook.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="customers-{tenant_id}.xlsx"'},
        )

    buf = io.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(row_values(r))
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="customers-{tenant_id}.csv"'},
    )


@router.get("/orders")
def list_tenant_orders(
    tenant_id: str,
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    q: str = Query(""),
    limit: int = Query(200, le=500),
    current_admin: dict = Depends(require_tenant_admin_permission("view_orders")),
):
    return tenant_list_orders(
        tenant_id=tenant_id,
        status=status,
        order_type=order_type,
        payment_status=payment_status,
        q=q,
        limit=limit,
    )


@router.get("/orders/stats")
def tenant_order_stats_route(
    tenant_id: str,
    current_admin: dict = Depends(require_tenant_admin_permission("view_orders")),
):
    return tenant_order_stats(tenant_id)


@router.get("/orders/{order_id}")
def get_tenant_order(
    tenant_id: str,
    order_id: str,
    current_admin: dict = Depends(require_tenant_admin_permission("view_orders")),
):
    row = tenant_get_order(tenant_id, order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order": row}


@router.put("/orders/{order_id}")
def update_tenant_order(
    tenant_id: str,
    order_id: str,
    body: OrderUpdate,
    current_admin: dict = Depends(require_tenant_admin_permission("manage_orders")),
):
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if body.status is not None and body.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if body.payment_status is not None and body.payment_status not in ALLOWED_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"payment_status must be one of {sorted(ALLOWED_PAYMENT_STATUSES)}")

    before = tenant_update_order(tenant_id, order_id, payload)
    if before is None:
        raise HTTPException(status_code=404, detail="Order not found")
    safe_fields = {key: value for key, value in payload.items() if key in {"status", "payment_status", "order_type"}}
    _record_audit(
        action="order_updated",
        actor=current_admin,
        resource_type="order",
        resource_id=before["id"],
        tenant_id=tenant_id,
        details={
            "order_number": before.get("order_number"),
            "changed_fields": sorted(safe_fields),
            "changes": {key: {"before": before.get(key), "after": value} for key, value in safe_fields.items()},
        },
    )
    return {"status": "ok", "order_id": order_id, "updated": payload}


@router.delete("/orders/{order_id}")
def delete_tenant_order(
    tenant_id: str,
    order_id: str,
    current_admin: dict = Depends(require_tenant_admin_permission("manage_orders")),
):
    row = tenant_delete_order(tenant_id, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")
    _record_audit(
        action="order_deleted",
        actor=current_admin,
        resource_type="order",
        resource_id=row["id"],
        tenant_id=tenant_id,
        details={
            "order_number": row.get("order_number"),
            "status": row.get("status"),
            "payment_status": row.get("payment_status"),
        },
    )
    return {"status": "ok", "order_id": order_id}