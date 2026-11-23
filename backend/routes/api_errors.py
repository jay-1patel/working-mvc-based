"""Admin API for persisted API/runtime errors (Backend Roadmap Phase 1).

Rows are written by services.error_reporter.report_error — the central
exception handler in backend/main.py reports every unhandled 500 here, so a
developer can find the exact failing API from this list (or from the
X-Request-Id / request_id quoted by the user) instead of grepping logs.

Access: super admins see every tenant's errors. A tenant admin sees ONLY
their own tenant's errors — the tenant filter is forced to their tenant
and asking for another tenant is refused with 403.
"""

from typing import Optional
from datetime import datetime, timezone
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from routes.auth import get_current_admin
from services.error_reporter import get_error, list_recent_errors, count_errors, report_error

router = APIRouter(tags=["api-errors"])


def _scoped_tenant_id(current_admin: dict, requested_tenant_id: Optional[str]) -> Optional[str]:
    role = current_admin.get("role")
    if role == "super_admin":
        return requested_tenant_id
    if role == "admin":
        own = str(current_admin.get("tenant_id") or "").strip()
        if not own:
            raise HTTPException(status_code=403, detail="Your admin account is not assigned to a tenant")
        requested = str(requested_tenant_id or "").strip()
        if requested and requested != own:
            raise HTTPException(status_code=403, detail="Admins can only view their own tenant's errors")
        return own
    raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/api/admin/errors")
def list_api_errors(
    limit: int = Query(50, ge=1, le=500),
    provider: Optional[str] = Query(None, description="Filter e.g. api, send2, groq"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant id"),
    current_admin: dict = Depends(get_current_admin),
    offset: int = 0,
    search: Optional[str] = None,
    severity: Optional[str] = None,
    http_status: Optional[int] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    """Recent API/runtime errors, newest first."""
    tenant_id = _scoped_tenant_id(current_admin, tenant_id)
    if offset < 0 or (search and len(search) > 200):
        raise HTTPException(status_code=422, detail='Invalid offset or search length')
    if severity not in (None, '', 'error', 'warning'):
        raise HTTPException(status_code=422, detail='Invalid severity')
    if http_status is not None and not 0 <= http_status <= 599:
        raise HTTPException(status_code=422, detail='Invalid HTTP status')
    def timestamp(value):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
        except ValueError:
            raise HTTPException(status_code=422, detail='Use an ISO date/time for date filters')
    filters = dict(provider=provider or None, tenant_id=tenant_id or None,
                   search=search, severity=severity or None, http_status=http_status,
                   since=timestamp(since), until=timestamp(until))
    rows = list_recent_errors(limit=limit, offset=offset, **filters)
    total = count_errors(**filters)
    return {"count": len(rows), "total": total, "offset": offset,
            "has_more": offset + len(rows) < total, "errors": rows}


@router.get("/api/admin/errors/{error_id}")
def get_api_error(
    error_id: int,
    current_admin: dict = Depends(get_current_admin),
):
    row = get_error(error_id)
    if not row:
        raise HTTPException(status_code=404, detail="Error log not found")
    if current_admin.get("role") == "admin":
        own = _scoped_tenant_id(current_admin, None)
        if str(row.get("tenant_id") or "") != str(own or ""):
            raise HTTPException(status_code=403, detail="Admins can only view their own tenant's errors")
    elif current_admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return row


class ClientError(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    detail: str = Field(default='', max_length=4000)
    page: str = Field(default='', max_length=300)
    api: str = Field(default='browser', max_length=200)
    request_id: Optional[str] = Field(default=None, pattern=r'^client_[a-f0-9-]{8,64}$')
    occurred_at: Optional[datetime] = None


_client_reports = defaultdict(deque)
_client_report_lock = Lock()


@router.post('/api/client-errors', status_code=202)
def report_client_error(body: ClientError, current_admin: dict = Depends(get_current_admin)):
    """Browser diagnostics, scoped by server identity, never client tenant input."""
    key = str(current_admin.get('username') or current_admin.get('id'))
    now = monotonic()
    with _client_report_lock:
        if len(_client_reports) > 5000:
            for old_key in list(_client_reports):
                if not _client_reports[old_key] or _client_reports[old_key][-1] < now - 60:
                    del _client_reports[old_key]
        recent = _client_reports[key]
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 30:
            raise HTTPException(status_code=429, detail='Too many browser error reports')
        recent.append(now)
    persisted = report_error('browser', body.api.split('?')[0], body.message,
                 tenant_id=current_admin.get('tenant_id'), request_id=body.request_id, notify=False,
                 detail=f"Page: {body.page.split('?')[0]}\nBrowser time: {body.occurred_at.isoformat() if body.occurred_at else 'unknown'}\n{body.detail}")
    if not persisted:
        raise HTTPException(status_code=503, detail='Error log storage is temporarily unavailable')
    return {'status': 'recorded'}
