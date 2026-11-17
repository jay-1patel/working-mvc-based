"""Tenant API onboarding requests and superadmin review."""

import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from database import get_db, get_db_context, record_admin_audit_event
from db.core import unique_violation_error_types, use_mongodb
from shared.tenancy import store as tenancy_store
from routes.auth import get_current_admin, has_permission

router = APIRouter(tags=["api-onboarding"])

ApiType = Literal["payment_api", "order_api"]
RequestStatus = Literal["pending", "approved", "rejected"]


class OnboardingRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    api_type: ApiType
    provider: str = Field(default="", max_length=100)
    environment: Literal["sandbox", "production"] = "sandbox"
    purpose: str = Field(min_length=10, max_length=2000)

    @field_validator("provider", "purpose")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("purpose")
    @classmethod
    def non_empty_purpose(cls, value: str) -> str:
        if len(value) < 10:
            raise ValueError("Purpose must be at least 10 characters")
        return value

    @field_validator("provider", "purpose")
    @classmethod
    def reject_likely_credentials(cls, value: str) -> str:
        # These are free-text descriptions, not a secret intake channel.
        if re.search(r"(?:sk_live_|sk_test_|api[_-]?key\s*[:=]|secret\s*[:=]|password\s*[:=])", value, re.IGNORECASE):
            raise ValueError("Do not include API keys, passwords, or secrets in this request")
        return value


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        value = value.strip()
        if re.search(r"(?:sk_live_|sk_test_|api[_-]?key\s*[:=]|secret\s*[:=]|password\s*[:=])", value, re.IGNORECASE):
            raise ValueError("Do not include credentials or secrets in the review note")
        return value


def _require_tenant_admin(admin: dict) -> str:
    """Only a tenant-bound admin with operation-management permission may request access."""
    if admin.get("role") not in ("admin", "sub_admin"):
        raise HTTPException(status_code=403, detail="Only tenant admins can submit API requests")
    tenant_id = str(admin.get("tenant_id") or "").strip()
    if not tenant_id or not has_permission(admin, "manage_operations"):
        raise HTTPException(status_code=403, detail="A tenant and manage_operations permission are required")
    return tenant_id


def _require_super_admin(admin: dict) -> None:
    # Do not use require_permission here: super admins bypass permissions while
    # tenant admins may be granted arbitrary permission switches.
    if admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access is required")


def _request_dict(row) -> dict:
    return dict(row)


_AUTH_BODY_KEYS = frozenset({"username", "session_id"})


async def _parse_body(request: Request, model):
    """Validate JSON after dropping panel auth fields the frontend always sends."""
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
    if isinstance(payload, dict):
        payload = {k: v for k, v in payload.items() if k not in _AUTH_BODY_KEYS}
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        errors = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors) from exc


def _add_event(
    conn,
    request_id: int,
    *,
    actor: dict,
    event_type: str,
    old_status: str | None,
    new_status: str,
    note: str = "",
) -> None:
    values = {
        "request_id": int(request_id),
        "actor_id": actor.get("id"),
        "actor_username": actor.get("username", ""),
        "actor_role": actor.get("role", ""),
        "event_type": event_type,
        "old_status": old_status,
        "new_status": new_status,
        "note": note,
    }
    if use_mongodb():
        from db.mongo import Repository

        Repository("api_onboarding_request_events").insert(values)
        return
    conn.execute(
        """INSERT INTO api_onboarding_request_events
           (request_id, actor_id, actor_username, actor_role, event_type,
            old_status, new_status, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            values["request_id"],
            values["actor_id"],
            values["actor_username"],
            values["actor_role"],
            values["event_type"],
            values["old_status"],
            values["new_status"],
            values["note"],
        ),
    )


def _with_eligible(rows: list) -> list:
    """Attach ``eligible`` like the SQL LEFT JOIN on api_onboarding_entitlements."""
    if not rows:
        return rows
    if not use_mongodb():
        return rows
    from db.mongo import Repository

    entitled = {
        int(e["request_id"])
        for e in Repository("api_onboarding_entitlements").find_all(
            {"request_id": {"$in": [int(r["id"]) for r in rows]}}
        )
    }
    out = []
    for row in rows:
        item = dict(row)
        item["eligible"] = 1 if int(item["id"]) in entitled else 0
        out.append(item)
    return out


@router.post("/api/integration-requests", status_code=201)
async def create_request(
    request: Request,
    current_admin: dict = Depends(get_current_admin),
):
    body = await _parse_body(request, OnboardingRequestCreate)
    return _create_request(body, current_admin)


def _create_request(body: OnboardingRequestCreate, current_admin: dict):
    tenant_id = _require_tenant_admin(current_admin)
    provider_lower = (body.provider or "").strip().lower()
    if not tenancy_store.get_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Your account is not assigned to an active tenant")

    if use_mongodb():
        from db.mongo import Repository

        repo = Repository("api_onboarding_requests")
        for existing in repo.find_all(
            {
                "tenant_id": tenant_id,
                "api_type": body.api_type,
                "status": {"$in": ["pending", "approved"]},
            }
        ):
            if (existing.get("provider") or "").strip().lower() == provider_lower:
                raise HTTPException(
                    status_code=409,
                    detail=f"A pending or approved request already exists for {body.provider}",
                )
        try:
            row = repo.insert(
                {
                    "tenant_id": tenant_id,
                    "api_type": body.api_type,
                    "provider": body.provider,
                    "environment": body.environment,
                    "purpose": body.purpose,
                    "status": "pending",
                    "requester_id": current_admin.get("id"),
                    "requester_username": current_admin.get("username", ""),
                    "decision_note": "",
                }
            )
        except unique_violation_error_types() as exc:
            if "api_onboarding_requests" in str(exc) or "duplicate key" in str(exc).lower():
                raise HTTPException(
                    status_code=409, detail=f"A request already exists for {body.provider}"
                ) from exc
            raise
        request_id = int(row["id"])
        _add_event(
            None,
            request_id,
            actor=current_admin,
            event_type="submitted",
            old_status=None,
            new_status="pending",
        )
        record_admin_audit_event(
            None,
            action="api_access_request_submitted",
            actor=current_admin,
            resource_type="api_access_request",
            resource_id=request_id,
            tenant_id=tenant_id,
            details={"api_type": body.api_type, "environment": body.environment},
        )
        row["eligible"] = 0
    else:
        with get_db_context() as conn:
            if not conn.execute("SELECT 1 FROM tenants WHERE id = ?", (tenant_id,)).fetchone():
                raise HTTPException(status_code=403, detail="Your account is not assigned to an active tenant")
            duplicate = conn.execute(
                """SELECT id FROM api_onboarding_requests
                   WHERE tenant_id = ? AND api_type = ? AND LOWER(provider) = LOWER(?) AND status IN ('pending', 'approved')""",
                (tenant_id, body.api_type, body.provider),
            ).fetchone()
            if duplicate:
                raise HTTPException(status_code=409, detail=f"A pending or approved request already exists for {body.provider}")
            try:
                cursor = conn.execute(
                    """INSERT INTO api_onboarding_requests
                       (tenant_id, api_type, provider, environment, purpose, status,
                        requester_id, requester_username)
                       VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                    (
                        tenant_id,
                        body.api_type,
                        body.provider,
                        body.environment,
                        body.purpose,
                        current_admin.get("id"),
                        current_admin.get("username", ""),
                    ),
                )
            except unique_violation_error_types() as exc:
                if "api_onboarding_requests" in str(exc) or "duplicate key" in str(exc).lower():
                    raise HTTPException(status_code=409, detail=f"A request already exists for {body.provider}") from exc
                raise
            request_id = cursor.lastrowid
            _add_event(
                conn,
                request_id,
                actor=current_admin,
                event_type="submitted",
                old_status=None,
                new_status="pending",
            )
            record_admin_audit_event(
                conn,
                action="api_access_request_submitted",
                actor=current_admin,
                resource_type="api_access_request",
                resource_id=request_id,
                tenant_id=tenant_id,
                details={"api_type": body.api_type, "environment": body.environment},
            )
            row = conn.execute(
                """SELECT r.*, 0 AS eligible FROM api_onboarding_requests r WHERE r.id = ?""",
                (request_id,),
            ).fetchone()
    return {"request": _request_dict(row)}


@router.get("/api/integration-requests")
def list_my_requests(current_admin: dict = Depends(get_current_admin)):
    tenant_id = _require_tenant_admin(current_admin)
    if use_mongodb():
        from db.mongo import Repository

        rows = Repository("api_onboarding_requests").find_all(
            {"tenant_id": tenant_id}, sort=[("created_at", -1), ("id", -1)]
        )
        return {"requests": [_request_dict(row) for row in _with_eligible(rows)]}
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT r.*, CASE WHEN e.request_id IS NULL THEN 0 ELSE 1 END AS eligible
               FROM api_onboarding_requests r
               LEFT JOIN api_onboarding_entitlements e ON e.request_id = r.id
               WHERE r.tenant_id = ? ORDER BY r.created_at DESC, r.id DESC""",
            (tenant_id,),
        ).fetchall()
        return {"requests": [_request_dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/api/admin/integration-requests")
def list_all_requests(
    status: RequestStatus | None = Query(default=None),
    current_admin: dict = Depends(get_current_admin),
):
    _require_super_admin(current_admin)
    if use_mongodb():
        from db.mongo import Repository

        flt = {"status": status} if status else None
        rows = Repository("api_onboarding_requests").find_all(
            flt, sort=[("created_at", -1), ("id", -1)]
        )
        return {"requests": [_request_dict(row) for row in _with_eligible(rows)]}
    conn = get_db()
    try:
        if status:
            rows = conn.execute(
                """SELECT r.*, CASE WHEN e.request_id IS NULL THEN 0 ELSE 1 END AS eligible
                   FROM api_onboarding_requests r
                   LEFT JOIN api_onboarding_entitlements e ON e.request_id = r.id
                   WHERE r.status = ? ORDER BY r.created_at DESC, r.id DESC""",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT r.*, CASE WHEN e.request_id IS NULL THEN 0 ELSE 1 END AS eligible
                   FROM api_onboarding_requests r
                   LEFT JOIN api_onboarding_entitlements e ON e.request_id = r.id
                   ORDER BY r.created_at DESC, r.id DESC"""
            ).fetchall()
        return {"requests": [_request_dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/api/admin/integration-requests/{request_id}/events")
def list_request_events(
    request_id: int,
    current_admin: dict = Depends(get_current_admin),
):
    _require_super_admin(current_admin)
    if use_mongodb():
        from db.mongo import Repository

        if not Repository("api_onboarding_requests").find_one({"id": int(request_id)}):
            raise HTTPException(status_code=404, detail="Request not found")
        rows = Repository("api_onboarding_request_events").find_all(
            {"request_id": int(request_id)}, sort=[("id", 1)]
        )
        return {"events": [_request_dict(row) for row in rows]}
    conn = get_db()
    try:
        if not conn.execute("SELECT 1 FROM api_onboarding_requests WHERE id = ?", (request_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Request not found")
        rows = conn.execute(
            """SELECT id, request_id, actor_id, actor_username, actor_role, event_type,
                      old_status, new_status, note, created_at
               FROM api_onboarding_request_events WHERE request_id = ? ORDER BY id""",
            (request_id,),
        ).fetchall()
        return {"events": [_request_dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/api/admin/integration-requests/{request_id}/decision")
async def decide_request(
    request_id: int,
    request: Request,
    current_admin: dict = Depends(get_current_admin),
):
    _require_super_admin(current_admin)
    body = await _parse_body(request, DecisionBody)
    if use_mongodb():
        from db.mongo import Repository

        reqs = Repository("api_onboarding_requests")
        row = reqs.find_one({"id": int(request_id)})
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be reviewed")

        decided_at = datetime.now(timezone.utc).isoformat()
        modified = reqs.update(
            {"id": int(request_id), "status": "pending"},
            {
                "status": body.decision,
                "reviewer_id": current_admin.get("id"),
                "reviewer_username": current_admin.get("username", ""),
                "decision_note": body.note,
                "decided_at": decided_at,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        if modified != 1:
            raise HTTPException(status_code=409, detail="Request was already reviewed")
        if body.decision == "approved":
            Repository("api_onboarding_entitlements").insert(
                {
                    "tenant_id": row["tenant_id"],
                    "api_type": row["api_type"],
                    "request_id": int(request_id),
                    "granted_by": current_admin.get("id"),
                    "granted_by_username": current_admin.get("username", ""),
                    "granted_at": decided_at,
                }
            )
        _add_event(
            None,
            request_id,
            actor=current_admin,
            event_type="decision",
            old_status="pending",
            new_status=body.decision,
            note=body.note,
        )
        record_admin_audit_event(
            None,
            action="api_access_request_reviewed",
            actor=current_admin,
            resource_type="api_access_request",
            resource_id=request_id,
            tenant_id=row["tenant_id"],
            details={"decision": body.decision, "api_type": row["api_type"]},
        )
        result = reqs.find_one({"id": int(request_id)})
        entitled = Repository("api_onboarding_entitlements").find_one(
            {"request_id": int(request_id)}
        )
        result["eligible"] = 1 if entitled else 0
    else:
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT status FROM api_onboarding_requests WHERE id = ?", (request_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Request not found")
            if row["status"] != "pending":
                raise HTTPException(status_code=409, detail="Only pending requests can be reviewed")

            decided_at = datetime.now(timezone.utc).isoformat()
            updated = conn.execute(
                """UPDATE api_onboarding_requests
                   SET status = ?, reviewer_id = ?, reviewer_username = ?, decision_note = ?,
                       decided_at = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status = 'pending'""",
                (
                    body.decision,
                    current_admin.get("id"),
                    current_admin.get("username", ""),
                    body.note,
                    decided_at,
                    request_id,
                ),
            )
            if updated.rowcount != 1:
                raise HTTPException(status_code=409, detail="Request was already reviewed")
            if body.decision == "approved":
                request = conn.execute(
                    "SELECT tenant_id, api_type FROM api_onboarding_requests WHERE id = ?",
                    (request_id,),
                ).fetchone()
                conn.execute(
                    """INSERT INTO api_onboarding_entitlements
                       (tenant_id, api_type, request_id, granted_by, granted_by_username, granted_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        request["tenant_id"],
                        request["api_type"],
                        request_id,
                        current_admin.get("id"),
                        current_admin.get("username", ""),
                        decided_at,
                    ),
                )
            _add_event(
                conn,
                request_id,
                actor=current_admin,
                event_type="decision",
                old_status="pending",
                new_status=body.decision,
                note=body.note,
            )
            request_meta = conn.execute(
                "SELECT tenant_id, api_type FROM api_onboarding_requests WHERE id = ?", (request_id,)
            ).fetchone()
            record_admin_audit_event(
                conn,
                action="api_access_request_reviewed",
                actor=current_admin,
                resource_type="api_access_request",
                resource_id=request_id,
                tenant_id=request_meta["tenant_id"],
                details={"decision": body.decision, "api_type": request_meta["api_type"]},
            )
            result = conn.execute(
                """SELECT r.*, CASE WHEN e.request_id IS NULL THEN 0 ELSE 1 END AS eligible
                   FROM api_onboarding_requests r
                   LEFT JOIN api_onboarding_entitlements e ON e.request_id = r.id
                   WHERE r.id = ?""",
                (request_id,),
            ).fetchone()
    return {
        "request": _request_dict(result),
        "message": (
            "Approved. Configure credentials through the secure setup process before enabling live traffic."
            if body.decision == "approved"
            else "Request rejected."
        ),
    }
