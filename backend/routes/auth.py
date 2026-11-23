import json
import logging
import re
import secrets
import hmac
import base64
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from core.send2_auth import (
    admin_username_candidates,
    decode_stored_username,
    encode_send2_username,
    normalize_login_username,
)

from database import (
    count_admins,
    create_admin as db_create_admin,
    delete_admin,
    get_admin_by_username,
    get_db_context,
    record_admin_audit_event,
    list_admin_records,
    count_admins_by_role,
    update_admin as db_update_admin,
    update_admin_email,
    update_admin_record,
)
from db.core import use_mongodb

logger = logging.getLogger("chiki_webhook")

# SECURITY FIX: Rate limiting for auth endpoints
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    import os as _os
    import sys as _sys
    _IS_TESTING = (
        "pytest" in _sys.modules
        or "unittest" in _sys.modules
        or any("pytest" in str(arg) or "unittest" in str(arg) for arg in _sys.argv)
        or _os.environ.get("TESTING", "").lower() in ("true", "1", "yes")
        or "PYTEST_CURRENT_TEST" in _os.environ
    )
    RATE_LIMIT_ENABLED = not _IS_TESTING
except ImportError:
    RATE_LIMIT_ENABLED = False
    logger.warning("slowapi not installed - rate limiting disabled. Install with: pip install slowapi")

# Configure limiter if available
limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED) if RATE_LIMIT_ENABLED else None

# SECURITY FIX: Password complexity requirements
MIN_PASSWORD_LENGTH = 12
MIN_PASSWORD_SCORE = 3  # 0-4 scale (zxcvbn)
# Rate limit exception handler. Registered on the FastAPI app in main.py --
# APIRouter has no exception_handler method.
async def rate_limit_exceeded_handler(request: Request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={"detail": f"Too many requests. Try again in {exc.detail} seconds."},
    )

router = APIRouter(prefix="/api/auth")
security = HTTPBasic(auto_error=False)

ALL_PERMISSIONS = {
    "manage_admins": "Manage admins (add/edit/delete)",
    "upload_faq": "Upload FAQ files",
    "upload_kb": "Upload KB files",
    "view_files": "View uploaded files",
    "delete_files": "Delete uploaded files",
    "view_products": "View products",
    "edit_delete_products": "Edit/delete products",
    "add_product": "Add products/services to the catalogue",
    "edit_product": "Edit catalogue entries",
    "delete_product": "Remove catalogue entries",
    "manage_services": "Add/edit/delete services",
    "manage_projects": "Edit the projects page",
    "manage_technologies": "Edit the technologies page",
    "manage_careers": "Edit the careers page",
    "manage_benefits": "Edit the benefits page",
    "manage_operations": "Manage operations (products, menus, prices, schemes, campaigns)",
    "chat": "Use admin chat",
    "chat_history": "View chat history",
    "catalogue_new_arrival": "Manage brochure and new releases",
    "view_orders": "View orders",
    "manage_orders": "Edit/delete orders",
    "view_complaints": "View complaints",
    "manage_complaints": "Handle complaints (reply/resolve)",
    "view_customers": "View customers",
    "view_analytics": "View analytics",
    "view_inbox": "Live inbox",
    "view_campaigns": "Campaigns",
    "manage_campaigns": "Create/edit/delete campaigns",
    "view_distributors": "Distributors",
    "manage_distributors": "Add/edit/delete distributors",
}

SUPER_ADMIN_PERMISSIONS = {k: True for k in ALL_PERMISSIONS}


# ---------- permission helpers ----------

def _parse_permissions(raw, default_all: bool = False) -> dict:
    perms = {k: default_all for k in ALL_PERMISSIONS}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = None
    if isinstance(raw, dict):
        for key in ALL_PERMISSIONS:
            if key in raw:
                perms[key] = bool(raw[key])
    return perms


def _effective_permissions(role: str, raw) -> dict:
    """Super admins always get everything; admins and sub admins get exactly
    what is stored. An admin is created with every permission on, and a super
    admin can then edit the switches down — the stored set is the truth."""
    if role == "super_admin":
        return dict(SUPER_ADMIN_PERMISSIONS)
    if role == "admin":
        # Rows that predate the permissions column (seeded with its '{}'
        # default) never chose a set — keep them fully enabled rather than
        # locking the tenant's admin out.
        empty = raw is None or raw == {} or (
            isinstance(raw, str) and raw.strip() in ("", "{}", "null")
        )
        if empty:
            return dict(SUPER_ADMIN_PERMISSIONS)
        return _parse_permissions(raw)
    return _parse_permissions(raw)


def has_permission(admin: dict, perm: str) -> bool:
    if not admin:
        return False
    if admin.get("role") == "super_admin":
        return True
    return bool(admin.get("permissions", {}).get(perm))


def require_permission(perm: str):
    def dependency(request: Request = None, current_admin: dict = Depends(get_current_admin)):
        if not has_permission(current_admin, perm):
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        if request is not None:
            ensure_super_admin_view_only(current_admin, request.method, request.url.path)
        return current_admin
    return dependency


def require_tenant_admin_permission(perm: str):
    """Tenant-scoped guard. A super admin sees every tenant; anyone else must
    be assigned to this exact tenant and hold `perm`."""
    def dependency(tenant_id: str, request: Request = None, current_admin: dict = Depends(get_current_admin)) -> dict:
        if not current_admin:
            raise HTTPException(status_code=403, detail="You do not have access to this tenant")
        if current_admin.get("role") == "super_admin":
            if request is not None:
                ensure_super_admin_view_only(current_admin, request.method, request.url.path)
            return current_admin
        if current_admin.get("tenant_id") != tenant_id:
            raise HTTPException(status_code=403, detail="You do not have access to this tenant")
        if not has_permission(current_admin, perm):
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return current_admin
    return dependency


def require_super_admin_permission(perm: str):
    """Platform-wide guard for the legacy global endpoints: super admins only."""
    def dependency(current_admin: dict = Depends(get_current_admin)) -> dict:
        if not current_admin or not has_permission(current_admin, perm) or current_admin.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Super admin access required")
        return current_admin
    return dependency


# ── Super-admin view-only guard (role-panels design, Phase 6 core) ─────────
# Decided rule: a super admin has system powers only — tenants, people,
# approvals, audit — and is VIEW-ONLY inside a tenant. They must never write
# a tenant's own data: no uploads, content edits, publishes, campaign sends,
# inbox replies, token mint/revoke or version rollbacks. Hiding the buttons
# in the console is not enforcement, so the check lives here, in the central
# permission helpers, plus a middleware twin in core/middleware.py for the
# routers that do not pass through these helpers.
#
# A super admin KEEPS (allowlist below): auth/people management, tenant
# creation and permanent tenant deletion, the active-test-tenant switch,
# approval decisions (tenant change requests + API access requests), and
# platform maintenance (log clearing, index rebuild). Everything else that
# writes tenant data is refused with 403 for a super-admin principal.
# Tenant-scoped API tokens are NOT admin principals and are unaffected:
# a tenant's own token keeps its publish/read capability for its tenant.

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

READ_ONLY_POST_PATHS = frozenset({
    "/api/admin/dashboard/overview",
    "/api/admin/errors",
    "/api/admin/tenants/conversations/detail",
    "/api/admin/tenants/chat/thread",
    "/api/admin/tenants/chat-history",
    "/api/admin/tenants/inbox",
    "/api/admin/tenants/agents",
    "/api/admin/tenants/complaints",
    "/api/admin/tenants/customers",
    "/api/admin/tenants/customers/export",
    "/api/admin/tenants/resolved",
    "/api/admin/tenants/crawl-runs",
    "/api/admin/tenants/crawl-runs/staged",
    "/api/admin/tenants/crawl-runs/export",
    "/api/admin/tenants/files",
    "/api/admin/tenants/files/preview",
    "/api/admin/tenants/files/download",
    "/api/admin/tenants/knowledge-gaps",
    "/api/admin/onboarding-kits/list",
    "/api/auth/admins",
})

BODY_TENANT_POST_PATHS = frozenset({
    "/api/admin/tenants/conversations/detail",
    "/api/admin/tenants/chat/thread",
    "/api/admin/tenants/chat-history",
    "/api/admin/tenants/inbox",
    "/api/admin/tenants/inbox/handover",
    "/api/admin/tenants/inbox/assign",
    "/api/admin/tenants/inbox/resolve",
    "/api/admin/tenants/inbox/reply",
    "/api/admin/tenants/inbox/attach",
    "/api/admin/tenants/agents",
    "/api/admin/tenants/complaints",
    "/api/admin/tenants/complaints/update",
    "/api/admin/tenants/complaints/reply",
    "/api/admin/tenants/complaints/delete",
    "/api/admin/tenants/customers",
    "/api/admin/tenants/customers/export",
    "/api/admin/tenants/resolved",
    "/api/admin/tenants/crawl",
    "/api/admin/tenants/crawl-runs",
    "/api/admin/tenants/crawl-runs/staged",
    "/api/admin/tenants/crawl-runs/export",
    "/api/admin/tenants/crawl-runs/approve",
    "/api/admin/tenants/crawl-runs/reject",
    "/api/admin/tenants/files",
    "/api/admin/tenants/files/upload",
    "/api/admin/tenants/files/bifurcate-existing",
    "/api/admin/tenants/files/preview",
    "/api/admin/tenants/files/download",
    "/api/admin/tenants/files/delete",
    "/api/admin/tenants/knowledge-gaps",
    "/api/admin/tenants/knowledge-gaps/resolve",
    "/api/admin/tenants/knowledge-gaps/create-faq",
})


# Path-param read POSTs that are not flat panel routes but must stay
# view-only for super admins (profile page load).
READ_ONLY_POST_PATH_PATTERNS = (
    re.compile(r"^/api/admin/tenants/[^/]+/detail$"),
    re.compile(r"^/api/admin/menus$"),
    re.compile(r"^/api/admin/menus/[^/]+$"),
    re.compile(r"^/api/admin/menus/[^/]+/settings$"),
)


def is_read_only_post(method: str, path: str) -> bool:
    if (method or "").upper() != "POST":
        return False
    if (path or "") in READ_ONLY_POST_PATHS:
        return True
    return any(pattern.match(path or "") for pattern in READ_ONLY_POST_PATH_PATTERNS)

SUPER_ADMIN_ALLOWED_WRITE_PATTERNS = (
    re.compile(r"^/api/auth(?:/.*)?$"),  # people management, own password, OTP
    re.compile(r"^/api/admin/tenants$"),  # POST: create a tenant
    re.compile(r"^/api/admin/tenants/active-test-tenant$"),
    re.compile(r"^/api/admin/tenants/[^/]+$"),  # DELETE only (checked below)
    re.compile(r"^/api/admin/tenant-change-requests/[^/]+/decision$"),
    re.compile(r"^/api/admin/integration-requests/[^/]+/decision$"),
    re.compile(r"^/api/admin/logs$"),  # platform maintenance
    re.compile(r"^/api/admin/rebuild-index$"),
    re.compile(r"^/faq/admin/rebuild$"),
)

# Path prefixes whose writes mutate a tenant's own data (tenant-scoped paths
# plus the legacy global single-tenant surfaces for the same data).
TENANT_DATA_WRITE_PREFIXES = (
    "/api/admin/tenants/",
    "/api/tenants/",
    "/api/admin/files",
    "/api/admin/products",
    "/api/admin/menus",
    "/api/admin/brochures",
    "/api/admin/upload",
    "/api/admin/analytics",
    "/api/admin/dynamic",
    "/api/admin/onboarding",
    "/api/admin/chat",
    "/api/complaints",
    "/api/inbox",
    "/api/orders",
    "/api/leads",
    "/catalog",
    # /api/test-simulator is capture-only diagnostics (no tenant publish /
    # approval surface) — super admins may use WhatsApp Tester.
    "/faq/admin",
)


def is_super_admin_allowed_write(method: str, path: str) -> bool:
    """System-power writes a super admin keeps, per the decided design."""
    method = (method or "").upper()
    if method not in WRITE_METHODS:
        return True
    for pattern in SUPER_ADMIN_ALLOWED_WRITE_PATTERNS:
        if pattern.match(path or ""):
            # The bare /api/admin/tenants/{id} pattern is the DELETE-tenant
            # system power only; a POST/PUT there is not a defined route.
            if pattern.pattern == r"^/api/admin/tenants/[^/]+$" and method != "DELETE":
                continue
            return True
    return False


def is_tenant_data_write(method: str, path: str) -> bool:
    """True when this request writes tenant data (vs a system power)."""
    method = (method or "").upper()
    if method not in WRITE_METHODS:
        return False
    if is_read_only_post(method, path):
        return False
    if is_super_admin_allowed_write(method, path):
        return False
    return any((path or "").startswith(prefix) for prefix in TENANT_DATA_WRITE_PREFIXES)


def ensure_super_admin_view_only(admin: dict | None, method: str, path: str) -> None:
    """Refuse a tenant-data write attempted by a super-admin principal."""
    if not admin or admin.get("role") != "super_admin":
        return
    if is_tenant_data_write(method, path):
        raise HTTPException(
            status_code=403,
            detail=(
                "Super admins are view-only inside tenants: this change must "
                "come from the tenant's admin (and is approved by you)."
            ),
        )


# ---------- helpers ----------

def _public_username(username: str | None) -> str:
    """Return the plain username clients send/receive (login-page form).

    DB rows store the Send2 Base64 form; API responses and session identity
    always use the decoded plain name. Does not accept Base64 as a login input
    path — use ``normalize_login_username`` for that.
    """
    return decode_stored_username(username)


def _resolve_admin_row(username: str) -> dict | None:
    """Find an admin: plain input → Base64 → match ``admins.username``.

    Callers must send the plain name (e.g. ``test_support_``). Base64 login
    input is rejected. Lookup uses the encoded form only.
    """
    try:
        candidates = admin_username_candidates(username)
    except ValueError:
        return None
    for candidate in candidates:
        row = get_admin_by_username(candidate)
        if row:
            return row
    return None


def _stored_username(row: dict | None, fallback: str = "") -> str:
    """Exact ``admins.username`` key for DB writes (may be Base64)."""
    if row and row.get("username") is not None:
        return str(row["username"])
    return str(fallback or "")


def _admin_from_pair(username: str, session_id: str, request: Request | None = None) -> dict:
    """Authenticate one live username/session-id pair from the database.

    Plain username only (same as ``/api/auth/login``): encode for DB lookup,
    then expose the plain name on the returned principal. Base64 input fails.
    """
    row = _resolve_admin_row(username)
    stored = str(row["session_id"] or "") if row else ""
    supplied = str(session_id or "")
    if not row or not stored or not hmac.compare_digest(stored, supplied):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    result = dict(row)
    result.pop("session_id", None)
    # DB stores Send2 Base64; session identity is always the plain name.
    result["username"] = _public_username(result.get("username") or username)
    result["role"] = result.get("role") or "sub_admin"
    result["permissions"] = _effective_permissions(result.get("role"), result.get("permissions"))
    if request is not None:
        request.state.current_admin = result
        request.state.error_tenant_id = result.get("tenant_id")
        from core.context import error_context_var
        trace_context = error_context_var.get()
        if trace_context is not None:
            trace_context["tenant_id"] = result.get("tenant_id")
    return result


def authenticate_basic_header(request: Request) -> dict:
    """Authenticate with username + session_id only (no Authorization required).

    Accepted sources, in order:
      1. Headers ``username`` + ``session_id``
      2. JSON/form body fields ``username`` + ``session_id`` (set by middleware)

    ``username`` must be the plain Send2/local name; lookup encodes it and
    matches Base64 ``admins.username`` (same rule as login).
    """
    cached = getattr(request.state, "current_admin", None)
    if cached:
        return cached

    username = (
        str(request.headers.get("username") or "").strip()
        or str(getattr(request.state, "auth_username", "") or "").strip()
    )
    session_id = (
        str(request.headers.get("session_id") or "").strip()
        or str(getattr(request.state, "auth_session_id", "") or "").strip()
    )
    if username and session_id:
        return _admin_from_pair(username, session_id, request)

    raise HTTPException(
        status_code=401,
        detail="Not authenticated — send username and session_id (header or JSON body)",
    )


def _admin_count() -> int:
    return count_admins()


def scoped_tenant_id(admin: dict) -> str | None:
    """Tenant a non-super caller is pinned to.

    ``None`` means the caller is a super admin and may read across tenants.
    A tenant admin or sub admin with no tenant assignment is refused.
    """
    if not admin:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if admin.get("role") == "super_admin":
        return None
    own = str(admin.get("tenant_id") or "").strip()
    if not own:
        raise HTTPException(status_code=403, detail="No tenant assigned")
    return own


def session_tenant_id(admin: dict | None = None, request: Request | None = None) -> str:
    """Tenant bound to the authenticated username/session_id — never from the body.

    Flat panel APIs resolve the working tenant only from the admin row matched
    by username + session_id. Callers must not send tenant_id in the JSON body.
    """
    if admin is None:
        if request is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        cached = getattr(request.state, "current_admin", None)
        admin = cached or get_current_admin(request, None)
    tid = str((admin or {}).get("tenant_id") or "").strip()
    if not tid:
        raise HTTPException(
            status_code=403,
            detail="No tenant assigned to this session — use a username/session_id bound to a tenant",
        )
    if request is not None:
        request.state.error_tenant_id = tid
    return tid


def get_current_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
) -> dict:
    cached = getattr(request.state, "current_admin", None)
    if cached:
        return cached
    if not credentials:
        return authenticate_basic_header(request)
    return _admin_from_pair(credentials.username, credentials.password, request)


def require_super_admin(current_admin: dict = Depends(get_current_admin)) -> dict:
    """Platform operator only. Tenant admins are not a substitute."""
    if not current_admin or current_admin.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_admin


# ── Tenant-scoped tokens (Phase 0.5) ──────────────────────────────────────
# A tenant token is an opaque secret stored only as a SHA-256 hash. It carries
# exactly one capability: publish/read that tenant's profile. Cross-tenant
# access is refused even when the token is valid.

def hash_tenant_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _raw_bearer(request: Request, credentials=None) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value if scheme.lower() == "bearer" and value else None


def get_tenant_principal(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
) -> dict | None:
    """Resolve the caller as a tenant principal, or None if not one.

    Returns {"type": "tenant", "tenant_id": ...} for a valid tenant token.
    Returns None (rather than raising) for anything else so the caller can fall
    back to the admin path.
    """
    raw = _raw_bearer(request, credentials)
    if not raw:
        return None
    from shared.tenancy import store as tenancy_store

    record = tenancy_store.get_tenant_token(hash_tenant_token(raw))
    if not record:
        return None
    return {
        "type": "tenant",
        "tenant_id": record["tenant_id"],
        "token_id": record["id"],
        "label": record.get("label", ""),
    }
def require_tenant_access():
    """Dependency: the caller must be an admin or THIS tenant's token.

    Enforces ``token.tenant_id == target`` (Phase 0.5). A super admin passes for
    any tenant; a sub admin needs manage_operations for tenant-data WRITES
    (reads only need the tenant binding plus the route's own view switch);
    a tenant token is bound to its own tenant and nothing else.

    ``tenant_id`` below is a path parameter: FastAPI fills it from the route
    (``/tenants/{tenant_id}/...``), so the check is always against the tenant
    actually addressed, never a value supplied in a request body.
    """
    def dependency(
        request: Request,
        tenant_id: str,
        credentials: HTTPBasicCredentials = Depends(security),
    ) -> dict:
        target = str(tenant_id or "").strip()
        if not target:
            raise HTTPException(status_code=400, detail="tenant_id is required")

        raw = _raw_bearer(request, credentials)
        # username + session_id may arrive as headers or JSON body (middleware).
        if not raw and not credentials and not getattr(request.state, "current_admin", None):
            header_user = str(request.headers.get("username") or "").strip()
            header_session = str(request.headers.get("session_id") or "").strip()
            if header_user and header_session:
                request.state.current_admin = _admin_from_pair(header_user, header_session, request)
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated — send username and session_id (header or JSON body)",
                )

        principal = get_tenant_principal(request, credentials) if raw else None
        if principal is not None:
            try:
                from backend.services.audit_context import set_audit_actor
                set_audit_actor(principal)
            except Exception:
                # deliberate: audit attribution is best-effort — the request
                # itself must not fail because the actor could not be stamped.
                logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
            if principal["tenant_id"] != target:
                logger.warning(
                    "Tenant token scope violation: token for %s tried to touch %s",
                    principal["tenant_id"], target,
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Token is scoped to tenant '{principal['tenant_id']}'",
                )
            return {
                "type": "tenant", "tenant_id": target,
                "token_id": principal.get("token_id"),
                "label": principal.get("label", ""),
            }

        admin = get_current_admin(request, credentials)
        # Super admins are view-only inside tenants (decided rule): refuse
        # tenant-data writes here, at the choke point every tenant-scoped
        # route passes through. Reads pass; system powers are allowlisted.
        ensure_super_admin_view_only(admin, request.method, request.url.path)
        try:
            from backend.services.audit_context import set_audit_actor
            set_audit_actor(admin)
        except Exception:
            # deliberate: audit attribution is best-effort — the request
            # itself must not fail because the actor could not be stamped.
            logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
        # manage_operations gates tenant-data WRITES only. Requiring it for
        # reads locked every sub-admin preset out of its own tenant's data:
        # none of the four presets (Support / Content / Operations / Growth)
        # grants manage_operations, yet their screens are read views of this
        # tenant (QA 2026-11-13). A bound sub admin may therefore READ; the
        # per-route view switches (view_files, view_products, chat_history,
        # ...) still apply on top of this gate. Writes keep the exact gate.
        if is_tenant_data_write(request.method, request.url.path) and not has_permission(admin, "manage_operations"):
            raise HTTPException(
                status_code=403, detail="You do not have permission to manage tenant profiles"
            )
        # Enforce tenant scoping for non-super-admins
        role = admin.get("role")
        if role != "super_admin":
            admin_tenant = str(admin.get("tenant_id") or "").strip()
            if admin_tenant and admin_tenant != target:
                raise HTTPException(
                    status_code=403, detail=f"Admin is scoped to tenant '{admin_tenant}'"
                )
            # If admin has no tenant_id set yet, they may still access (backcompat) but better to scope
        return {
            "type": "admin",
            "id": admin.get("id"),
            "username": admin.get("username", ""),
            "role": admin.get("role", ""),
            "tenant_id": admin.get("tenant_id"),
            "permissions": admin.get("permissions", {}),
        }

    return dependency


def authorize_tenant_access(
    request: Request,
    tenant_id: str,
    credentials: HTTPBasicCredentials = None,
) -> dict:
    """Authorize a tenant selected in a JSON body instead of a path param."""
    target = str(tenant_id or "").strip()
    request.state.error_tenant_id = target or None
    try:
        from core.context import error_context_var
        context = error_context_var.get()
        if context is not None:
            context["tenant_id"] = target or None
    except Exception:
        pass
    return require_tenant_access()(request, tenant_id, credentials)




# ---------- request schemas ----------

class LoginRequest(BaseModel):
    # Plain Send2 / local username only (e.g. ``test_support_``). Backend
    # Base64-encodes it and matches ``admins.username`` (Base64) + session_id.
    # Base64 input is rejected.
    username: str
    session_id: str


class CreateAdminRequest(BaseModel):
    username: str
    # Omitted → forced by creator role (super_admin→admin, admin→sub_admin).
    role: Optional[str] = None
    permissions: Optional[dict] = None
    email: Optional[str] = None
    tenant_id: Optional[str] = None


class UpdateAdminRequest(BaseModel):
    role: Optional[str] = None
    permissions: Optional[dict] = None
    email: Optional[str] = None
    tenant_id: Optional[str] = None


# ---------- routes ----------

@router.get("/status")
def auth_status():
    """Public: returns whether any admin accounts exist."""
    return {"has_admins": _admin_count() > 0}


@router.post("/login")
# SECURITY FIX: Rate limiting - 5 requests per minute for login attempts
@limiter.limit("5/minute") if RATE_LIMIT_ENABLED else lambda f: f
async def admin_login(request: Request, body: LoginRequest):
    """Authenticate a plain username plus its live session ID.

    Callers must pass the decoded Send2 name (``test_support_``). The backend
    Base64-encodes it and matches ``admins.username`` (Base64 only) together
    with ``session_id``. Pasting an already-encoded username fails.
    """
    try:
        username = normalize_login_username(body.username)
    except ValueError:
        # Keep Base64 / malformed input indistinguishable from an unknown
        # account while still recording the failed attempt via audit.
        username = ""
    supplied_session = str(body.session_id or "").strip()
    admin = _resolve_admin_row(username) if username else None

    stored = str((admin or {}).get("session_id") or "")
    session_matches = bool(stored and supplied_session and hmac.compare_digest(stored, supplied_session))

    if not admin or not session_matches:
        failure_audit = dict(
            action="login",
            actor={"username": username[:100], "role": admin.get("role") if admin else None},
            outcome="failure",
            resource_type="admin_session",
            target_username=username[:100],
            tenant_id=admin.get("tenant_id") if admin else None,
            details={"reason": "invalid_credentials"},
        )
        if use_mongodb():
            record_admin_audit_event(None, **failure_audit)
        else:
            with get_db_context() as conn:
                record_admin_audit_event(conn, **failure_audit)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    admin_dict = dict(admin)
    admin_dict.pop("session_id", None)
    # Always expose the plain username to the client / session store.
    admin_dict["username"] = username
    # Send2-synced rows sometimes omit role; default safely so login never 500s.
    role = admin_dict.get("role") or "sub_admin"
    admin_dict["role"] = role
    permissions = _effective_permissions(role, admin_dict.get("permissions"))
    admin_dict["permissions"] = permissions
    success_audit = dict(
        action="login",
        actor={**admin_dict, "username": admin_dict["username"][:100]},
        resource_type="admin_session",
        target_username=admin_dict["username"][:100],
        tenant_id=admin_dict.get("tenant_id"),
    )
    if use_mongodb():
        record_admin_audit_event(None, **success_audit)
    else:
        with get_db_context() as conn:
            record_admin_audit_event(conn, **success_audit)
    logger.info(f"Admin logged in: {admin_dict['username']}")
    return {
        "status": "ok",
        "token": base64.b64encode(
            f"{admin_dict['username']}:{stored}".encode("utf-8")
        ).decode("ascii"),
        "username": admin_dict["username"],
        "session_id": stored,
        "role": role,
        "permissions": permissions,
        "tenant_id": admin_dict.get("tenant_id"),
    }


@router.post("/create")
def create_admin(body: CreateAdminRequest, current_admin: dict = Depends(get_current_admin)):
    """Create a new admin. Requires the manage_admins permission."""
    if not has_permission(current_admin, "manage_admins"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage admins",
        )
    if _admin_count() == 0:
        raise HTTPException(
            status_code=403,
            detail="No admins exist yet. Use /api/auth/first-admin first.",
        )

    # Normalize an explicit role; omitted role is filled from the creator hierarchy.
    role = (body.role or "").strip()
    if role in ("subadmin", "sub-admin"):
        role = "sub_admin"
    elif role in ("superadmin", "super-admin"):
        role = "super_admin"

    current_role = current_admin.get("role")
    # Hierarchy: superadmin creates company admins only; company admins create
    # sub-admins only. Multiple company admins may share the same tenant_id.
    if current_role == "super_admin":
        if role == "sub_admin":
            raise HTTPException(
                status_code=403,
                detail="A super admin can create company admins only",
            )
        if role == "super_admin":
            raise HTTPException(status_code=403, detail="There can be only one super admin")
        role = "admin"
    elif current_role == "admin":
        if role in ("admin", "super_admin"):
            raise HTTPException(
                status_code=403,
                detail="A company admin can create sub-admins only",
            )
        role = "sub_admin"
    else:
        raise HTTPException(
            status_code=403,
            detail="Only a super admin or company admin can create accounts",
        )

    # A new admin starts with every permission on (default_all=True); the
    # super admin can then edit the switches. Sub admins start with none.
    permissions = (
        dict(SUPER_ADMIN_PERMISSIONS)
        if role == "super_admin"
        else _parse_permissions(body.permissions, default_all=(role == "admin"))
    )

    email = (body.email or "").strip() or None

    # Determine tenant scope
    tenant_id = body.tenant_id
    if tenant_id is not None and isinstance(tenant_id, str):
        tenant_id = tenant_id.strip() or None
    if current_role != "super_admin":
        # Only a super admin chooses the tenant; every other creator is
        # strictly scoped to their own tenant.
        tenant_id = current_admin.get("tenant_id")

    try:
        plain_username = normalize_login_username(body.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "Invalid username") from exc

    try:
        session_id = secrets.token_urlsafe(32)
        # Store the Send2 Base64 form so login (plain → encode → lookup) matches.
        stored_username = encode_send2_username(plain_username)
        admin_id = db_create_admin(
            stored_username,
            role=role,
            permissions=permissions,
            tenant_id=tenant_id,
            session_id=session_id,
            email=email,
        )
        audit_kwargs = dict(
            action="admin_created",
            actor=current_admin,
            resource_type="admin",
            resource_id=admin_id,
            target_username=plain_username,
            tenant_id=tenant_id,
            details={
                "role": role,
                "created_admin": {
                    "username": plain_username,
                    "role": role,
                    "permissions": permissions,
                    "email": email,
                    "tenant_id": tenant_id,
                },
            },
        )
        if use_mongodb():
            record_admin_audit_event(None, **audit_kwargs)
        else:
            with get_db_context() as conn:
                record_admin_audit_event(conn, **audit_kwargs)
    except Exception:
        raise HTTPException(status_code=409, detail="Username already taken")

    logger.info(f"Admin created by {current_admin['username']}: {plain_username} ({role})")
    return {"status": "ok", "username": plain_username, "session_id": session_id,
            "role": role, "permissions": permissions, "email": email,
            "tenant_id": tenant_id, "created_by": current_admin["username"]}


def _admin_target(username: str, current_admin: dict) -> dict | None:
    """Resolve an admin target without exposing other tenants' accounts.

    Path/body usernames arrive in plain form (same as login); match encoded or
    plain ``admins.username`` rows, then enforce tenant scope.
    """
    row = _resolve_admin_row(username)
    if not row:
        return None
    if current_admin.get("role") == "super_admin":
        return row
    tenant_id = str(current_admin.get("tenant_id") or "").strip()
    if not tenant_id:
        return None
    if str(row.get("tenant_id") or "").strip() != tenant_id:
        return None
    return row


def _admin_write_scope(current_admin: dict) -> tuple[str, list]:
    """SQL predicate and params that keep non-super-admin writes tenant-bound."""
    if current_admin.get("role") == "super_admin":
        return "", []
    tenant_id = str(current_admin.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Your admin account is not assigned to a tenant")
    return " AND tenant_id = ?", [tenant_id]


def _ensure_super_not_touching_tenant_account(current_admin: dict, target: dict) -> None:
    """Super admins are view-only inside tenants (decided rule) — that also
    covers account administration. The central view-only guard allowlists
    /api/auth/* (login, OTP, self-service), which let a super admin reset a
    TENANT user's password and take over the account (QA D-05, 2026-11-13).
    Account-admin endpoints (update / delete / password reset) may therefore
    be used by a super admin only on platform-level accounts (super_admin
    role or no tenant binding); a tenant-bound account is administered by
    that tenant's own admin."""
    if current_admin.get("role") != "super_admin":
        return
    if str(target.get("tenant_id") or "").strip():
        raise HTTPException(
            status_code=403,
            detail="Super admins are view-only inside tenants and cannot modify tenant accounts",
        )


def _list_admins_payload(current_admin: dict) -> dict:
    """Build the admin roster payload (plain usernames)."""
    if current_admin.get("role") == "super_admin":
        records = list_admin_records()
    else:
        tenant_id = str(current_admin.get("tenant_id") or "").strip()
        records = list_admin_records(tenant_id=tenant_id, include_all=False)
        records = [
            a for a in records
            if str(a.get("role") or "").strip() in ("admin", "sub_admin")
        ]
    result = []
    for a in records:
        result.append({
            "username": _public_username(a.get("username")),
            "email": a.get("email"),
            "role": a["role"],
            "permissions": _effective_permissions(a["role"], a["permissions"]),
            "created_at": a.get("created_at"),
            "tenant_id": a.get("tenant_id"),
        })
    return {"admins": result}


@router.api_route("/admins", methods=["GET", "POST"])
def list_admins(current_admin: dict = Depends(require_permission("manage_admins"))):
    """List the caller's tenant admins; super admins retain the global roster.

    Super admins see every account. Tenant admins see only ``admin`` and
    ``sub_admin`` accounts in their tenant — never ``super_admin`` rows.

    Panel clients should use ``POST /api/auth/admins`` with plain
    ``username`` + ``session_id`` (same as login). GET remains for older tools.
    """
    return _list_admins_payload(current_admin)


@router.patch("/admins/{username}")
def update_admin(username: str, body: UpdateAdminRequest, current_admin: dict = Depends(get_current_admin)):
    """Update an admin's permissions, email or tenant scope.

    A role is fixed at account creation and can NEVER be changed through
    this endpoint (decided rule, 2026-11-10): to give someone a different
    role, delete the account and create a new one with the correct role.
    A ``role`` value that differs from the account's current role is
    refused with 403; the same value is treated as a no-op.
    Requires the manage_admins permission.
    """
    if not has_permission(current_admin, "manage_admins"):
        raise HTTPException(status_code=403, detail="You do not have permission to manage admins")

    target = _admin_target(username, current_admin)
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
    _ensure_super_not_touching_tenant_account(current_admin, target)

    stored_username = _stored_username(target, username)
    public_username = _public_username(stored_username)
    is_self = public_username == _public_username(current_admin.get("username"))

    if is_self and (body.role is not None or body.permissions is not None):
        raise HTTPException(
            status_code=403,
            detail="You cannot change your own role or permissions. Ask another admin with manage admins permission.",
        )

    if body.role is not None:
        requested_role = body.role
        if requested_role in ("superadmin", "super-admin"):
            requested_role = "super_admin"
        elif requested_role in ("subadmin", "sub-admin"):
            requested_role = "sub_admin"
        if requested_role != target["role"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Roles are fixed at account creation and cannot be changed. "
                    "Delete this account and create a new one with the correct role."
                ),
            )
    new_role = target["role"]

    if body.permissions is not None:
        permissions = _parse_permissions(body.permissions, default_all=False)
    else:
        permissions = _parse_permissions(target["permissions"])

    if new_role == "super_admin":
        permissions = dict(SUPER_ADMIN_PERMISSIONS)

    # Only a super admin may re-scope an admin to another tenant; for everyone
    # else tenant_id is left untouched (None means "no change" here).
    tenant_id = body.tenant_id if current_admin.get("role") == "super_admin" else None

    after_tenant = tenant_id if tenant_id is not None else target.get("tenant_id")

    before = {
        "role": target.get("role"),
        "permissions": target.get("permissions") or {},
        "tenant_id": target.get("tenant_id"),
        "email": target.get("email"),
    }
    email = body.email.strip() or None if body.email is not None else before["email"]
    after_tenant = tenant_id if tenant_id is not None else before["tenant_id"]
    update_admin_record(stored_username, role=new_role, permissions=permissions, tenant_id=tenant_id)
    if body.email is not None:
        update_admin_email(stored_username, email)
    changed_permissions = sorted(
        key for key in set(before["permissions"]) | set(permissions)
        if bool(before["permissions"].get(key)) != bool(permissions.get(key))
    )
    audit_kwargs = dict(
        action="admin_updated",
        actor=current_admin,
        resource_type="admin",
        resource_id=target.get("id"),
        target_username=public_username,
        tenant_id=after_tenant,
        details={
            "changed_fields": [
                field for field, old, new in (
                    ("role", before["role"], new_role),
                    ("permissions", before["permissions"], permissions),
                    ("tenant_id", before["tenant_id"], after_tenant),
                    ("email", before["email"], email),
                ) if old != new and (field != "email" or body.email is not None)
            ],
            "role_before": before["role"],
            "role_after": new_role,
            "tenant_id_before": before["tenant_id"],
            "tenant_id_after": after_tenant,
            "permission_keys_changed": changed_permissions,
            "permissions_before": before["permissions"],
            "permissions_after": permissions,
        },
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit_kwargs)
    else:
        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit_kwargs)

    logger.info(f"Admin updated by {current_admin['username']}: {public_username} ({new_role})")
    return {"status": "ok", "username": public_username, "role": new_role, "permissions": permissions}


@router.delete("/admins/{username}")
def delete_admin_endpoint(username: str, current_admin: dict = Depends(get_current_admin)):
    """Delete an admin account. Requires the manage_admins permission."""
    if not has_permission(current_admin, "manage_admins"):
        raise HTTPException(status_code=403, detail="You do not have permission to manage admins")

    if _public_username(username) == _public_username(current_admin.get("username")):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target = _admin_target(username, current_admin)
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
    _ensure_super_not_touching_tenant_account(current_admin, target)

    if target["role"] == "super_admin":
        raise HTTPException(status_code=403, detail="Super admin accounts cannot be deleted")

    stored_username = _stored_username(target, username)
    public_username = _public_username(stored_username)
    delete_admin(stored_username)
    deleted_admin = dict(target)
    deleted_admin["username"] = public_username
    audit_kwargs = dict(
        action="admin_deleted",
        actor=current_admin,
        resource_type="admin",
        resource_id=target.get("id"),
        target_username=public_username,
        tenant_id=target.get("tenant_id"),
        details={"role": target.get("role"), "deleted_admin": deleted_admin},
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit_kwargs)
    else:
        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit_kwargs)
    logger.info(f"Admin deleted by {current_admin['username']}: {public_username}")
    return {"status": "ok", "username": public_username}


@router.post("/admins/{username}/regenerate-session")
def regenerate_admin_session(username: str, current_admin: dict = Depends(get_current_admin)):
    """Replace a session id. Super admins may target anyone; others only self."""
    public_request = _public_username(username)
    if (
        current_admin.get("role") != "super_admin"
        and public_request != _public_username(current_admin.get("username"))
    ):
        raise HTTPException(status_code=403, detail="You may only regenerate your own session ID")
    target = _resolve_admin_row(username)
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
    stored_username = _stored_username(target, username)
    public_username = _public_username(stored_username)
    session_id = secrets.token_urlsafe(32)
    if not db_update_admin(stored_username, session_id=session_id):
        raise HTTPException(status_code=404, detail="Admin not found")
    audit_kwargs = dict(
        action="admin_session_regenerated",
        actor=current_admin,
        resource_type="admin",
        resource_id=target.get("id"),
        target_username=public_username,
        tenant_id=target.get("tenant_id"),
        details={"changed_fields": ["session_id"]},
    )
    if use_mongodb():
        record_admin_audit_event(None, **audit_kwargs)
    else:
        with get_db_context() as conn:
            record_admin_audit_event(conn, **audit_kwargs)
    logger.info("Admin session ID regenerated for %s by %s", public_username, current_admin["username"])
    return {"status": "ok", "username": public_username, "session_id": session_id}


def _onboarding_approved(admin: dict) -> bool:
    """Whether this company admin has cleared first-time onboarding.

    Only the company ``admin`` role is gated. An admin is cleared once a super
    admin approves one of the tenant change requests they filed from the
    "Register a tenant" panel. Super admins and sub admins are never gated.
    """
    if admin.get("role") != "admin":
        return True
    # Session principal is plain; requests may have been stored plain or Base64.
    plain = _public_username(admin.get("username"))
    names: list[str] = []
    if plain:
        names.append(plain)
        try:
            encoded = encode_send2_username(plain)
            if encoded not in names:
                names.append(encoded)
        except ValueError:
            pass
    if not names:
        return False
    if use_mongodb():
        from db.mongo import Repository

        row = Repository("tenant_change_requests").find_one(
            {"requester_username": {"$in": names}, "status": "approved"}
        )
        return row is not None
    placeholders = ",".join("?" for _ in names)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT 1 FROM tenant_change_requests "
            f"WHERE requester_username IN ({placeholders}) AND status = 'approved' LIMIT 1",
            names,
        ).fetchone()
    return row is not None


@router.get("/me")
def admin_me(current_admin: dict = Depends(get_current_admin)):
    """Return the currently authenticated admin."""
    return {
        "username": _public_username(current_admin.get("username")),
        "role": current_admin["role"],
        "permissions": current_admin["permissions"],
        "tenant_id": current_admin.get("tenant_id"),
        "onboarding_approved": _onboarding_approved(current_admin),
    }
