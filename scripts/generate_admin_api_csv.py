"""
Admin vs Superadmin panel APIs (from image.png + onboarding screenshots).

SHARED sidebar (both roles):
  Dashboard · Chats · Profile · WhatsApp · Website crawler · Customers

SUPERADMIN EXTRA (Manage):
  People / privileges · Business requests · Activity log · Errors & health

Privilege rule:
  - Admin: can EDIT profile/menu/customers/crawler and SUBMIT publish requests
  - Superadmin (view-only in tenant): can READ same pages, APPROVE/REJECT
    business requests — cannot edit profile/menu unless support Login

Columns: page_type, page, subpage, roles, http_method, api_path, curl,
         date_made, who_made, date_combined, who_combined, screenshot, notes
"""
from __future__ import annotations

import csv
from pathlib import Path

BASE = "http://127.0.0.1:9000"
UID = "USER_ID"
SID = "SESSION_ID"
TID = "c"
WA = "919999999999"

DATE_COMBINED = "2026-11-25"
WHO_COMBINED = "japan"
DATE_MADE = "2026-11-25"
WHO_MADE = "team"

AUTH_H = f'-H "user_id: {UID}" -H "session_id: {SID}" -H "Accept: application/json"'
AUTH_JSON = f'-H "Content-Type: application/json" {AUTH_H}'


def _auth_body(body: str) -> str:
    b = body.strip()
    if b.startswith("{") and b.endswith("}"):
        inner = b[1:-1].strip()
        auth = f'"user_id": "{UID}", "session_id": "{SID}"'
        return "{" + (auth + (", " + inner if inner else "")) + "}"
    return body


def curl_post(path: str, body: str = "{}", qs: str = "") -> str:
    return f"curl -s -X POST {AUTH_JSON} -d '{_auth_body(body)}' \"{BASE}{path}{qs}\""


def curl_get(path: str, qs: str = "") -> str:
    return f'curl -s -X GET {AUTH_H} "{BASE}{path}{qs}"'


def curl_multipart(path: str, fields: str) -> str:
    return f'curl -s -X POST -H "user_id: {UID}" -H "session_id: {SID}" {fields} "{BASE}{path}"'


rows: list[dict] = []


def add(
    page_type: str,
    page: str,
    subpage: str,
    roles: str,
    method: str,
    path: str,
    curl: str,
    screenshot: str = "",
    notes: str = "",
):
    rows.append(
        {
            "page_type": page_type,
            "page": page,
            "subpage": subpage,
            "roles": roles,
            "http_method": method,
            "api_path": path,
            "curl": curl,
            "date_made": DATE_MADE,
            "who_made": WHO_MADE,
            "date_combined": DATE_COMBINED,
            "who_combined": WHO_COMBINED,
            "screenshot": screenshot,
            "notes": notes,
        }
    )


# Captured from http://localhost:5173/?mock=1 via scripts/capture_admin_screenshots.mjs
SHOT_LOGIN = "images/admin-login.png"
SHOT_DASH = "images/admin-dashboard.png"
SHOT_CHATS = "images/admin-chats.png"
SHOT_PROFILE = "images/admin-profile.png"
SHOT_WA_MENU = "images/admin-whatsapp-menu.png"
SHOT_PROF_MENU = "images/admin-profile-menu.png"
SHOT_WA_SET = "images/admin-whatsapp-settings.png"
SHOT_CRAWL = "images/admin-website-crawler.png"
SHOT_CUST = "images/admin-customers.png"
SHOT = SHOT_DASH  # default shared sidebar look
SHOT_SA = "image.png → Manage (superadmin extra)"
SHOT_ONB = "images/onboarding"

# ═══════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════
add(
    "Auth",
    "Login",
    "Sign in",
    "all",
    "POST",
    "/api/auth/login",
    f"curl -s -X POST -H \"Content-Type: application/json\" -d '{{\"username\":\"YOUR_USER\",\"session_id\":\"YOUR_SESSION\"}}' \"{BASE}/api/auth/login\"",
    SHOT_LOGIN,
    "Copy user_id + session_id into later curls",
)
add("Auth", "Login", "Current identity", "all", "POST", "/api/auth/me", curl_post("/api/auth/me"), SHOT_LOGIN)
add("Auth", "Login", "Empty-DB gate", "all", "POST", "/api/auth/status", curl_post("/api/auth/status"), SHOT_LOGIN)

# ═══════════════════════════════════════════════════════════════════════════
# ONBOARDING (admin first-login)
# ═══════════════════════════════════════════════════════════════════════════
FIRST_LOGIN_BODY = (
    "{"
    '"tenant_id":"wanderly-travels","slug":"wanderly-travels","vertical":"tours_travel",'
    '"display_name":"Wanderly Travels","website":"https://example.com",'
    '"waba_phone_id":"+919876543210","mobile_number":"+919876543210",'
    '"snapshot":{'
    '"brand":{"name":"Wanderly Bot","tagline":"Software that ships","signature":"— Team Leeway",'
    '"support_email":"support@wanderly.test","support_phone":"+919876543210",'
    '"menu_greeting":"Hi! I\'m Wanderly Bot from Wanderly Travels. How can I help?"},'
    '"hours":{"timezone":"Asia/Kolkata","always_open":true,"opens":"09:00","closes":"21:00"},'
    '"notifications":{"sales_email":"sales@wanderly.test","support_email":"support@example.com"},'
    '"guardrails":{"forbidden_terms":[],"handoff_keywords":["human","agent","person"],'
    '"escalate_on":[],"escalation_message":"Let me connect you with our team."},'
    '"business":{"destinations":[],"trip_types":[],"policy":"","seasonality":""}'
    "}"
    "}"
)

for step, shot, note in [
    ("1 WhatsApp", "01-whatsapp.png", "phone + hours"),
    ("2 Company", "02-company.png", "company + vertical"),
    ("3 Brand & voice", "03-brand.png", "bot name / greeting"),
    ("4 Your business", "04-your-business-modules.png", "modules / destinations"),
    ("5 Notifications", "05-notifications.png", "enquiry emails"),
    ("6 Guardrails", "06-guardrails.png", "handoff keywords"),
    ("7 Review — Finish setup", "07-review.png", "Creates tenant + publishes v1"),
]:
    add(
        "Onboarding (admin)",
        "Set up chatbot",
        step,
        "admin (unbound)",
        "POST",
        "/api/auth/first-login/complete",
        curl_post("/api/auth/first-login/complete", FIRST_LOGIN_BODY),
        f"{SHOT_ONB}-{shot}",
        f"UI step only until Finish — {note}",
    )

add(
    "Onboarding (admin)",
    "Set up chatbot",
    "List tenants (id conflict check)",
    "admin",
    "POST",
    "/api/admin/tenants/list",
    curl_post("/api/admin/tenants/list"),
    f"{SHOT_ONB}-02-company.png",
    "",
)

# ═══════════════════════════════════════════════════════════════════════════
# SHARED READ bootstrap (both)
# ═══════════════════════════════════════════════════════════════════════════
add(
    "Shared (admin + superadmin)",
    "Tenant bootstrap",
    "Resolved live profile (READ)",
    "admin,super_admin",
    "POST",
    "/api/admin/tenants/resolved",
    curl_post("/api/admin/tenants/resolved"),
    SHOT,
    "Both roles — session tenant",
)
add(
    "Shared (admin + superadmin)",
    "Tenant bootstrap",
    "Detail / draft layers (READ)",
    "admin,super_admin",
    "POST",
    f"/api/admin/tenants/{TID}/detail",
    curl_post(f"/api/admin/tenants/{TID}/detail"),
    SHOT,
    "SA uses this to review pending edits; admin uses it to edit",
)

# ═══════════════════════════════════════════════════════════════════════════
# ADMIN — shared sidebar pages WITH EDIT / WRITE
# ═══════════════════════════════════════════════════════════════════════════

# Dashboard
add("Admin", "Dashboard", "Send2 credentials status", "admin", "POST", "/api/admin/tenants/send2-credentials/status", curl_post("/api/admin/tenants/send2-credentials/status"), SHOT, "#/tenants/:id/overview")
add("Admin", "Dashboard", "Inbox preview", "admin", "POST", "/api/admin/tenants/inbox", curl_post("/api/admin/tenants/inbox", '{"include_resolved":false}'), SHOT, "")
add("Admin", "Dashboard", "Today chat history", "admin", "POST", "/api/admin/tenants/chat-history", curl_post("/api/admin/tenants/chat-history", '{"days":1,"limit":500}'), SHOT, "")
add("Admin", "Dashboard", "Crawl runs", "admin", "POST", "/api/admin/tenants/crawl-runs", curl_post("/api/admin/tenants/crawl-runs"), SHOT, "")
add("Admin", "Dashboard", "Staged crawl pages", "admin", "POST", "/api/admin/tenants/crawl-runs/staged", curl_post("/api/admin/tenants/crawl-runs/staged", '{"run_id":1}'), SHOT, "")
add("Admin", "Dashboard", "Customers preview", "admin", "POST", "/api/admin/tenants/customers", curl_post("/api/admin/tenants/customers", '{"limit":50}'), SHOT, "")
add("Admin", "Dashboard", "Errors strip", "admin", "POST", "/api/admin/errors", curl_post("/api/admin/errors", "{}", f"?limit=100&tenant_id={TID}"), SHOT, "")

# Chats — admin can act
add("Admin", "Chats", "Inbox list", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox", curl_post("/api/admin/tenants/inbox", '{"include_resolved":true}'), SHOT, "#/tenants/:id/inbox")
add("Admin", "Chats", "Conversations list", "admin (view_inbox)", "POST", "/api/admin/tenants/conversations", curl_post("/api/admin/tenants/conversations", '{"limit":500}'), SHOT, "")
add("Admin", "Chats", "Load thread", "admin (view_inbox)", "POST", "/api/admin/tenants/chat/thread", curl_post("/api/admin/tenants/chat/thread", f'{{"wa_id":"{WA}","limit":300}}'), SHOT, "")
add("Admin", "Chats", "List agents", "admin (view_inbox)", "POST", "/api/admin/tenants/agents", curl_post("/api/admin/tenants/agents"), SHOT, "")
add("Admin", "Chats", "Reply (WRITE)", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox/reply", curl_post("/api/admin/tenants/inbox/reply", f'{{"wa_id":"{WA}","message":"Hello from admin"}}'), SHOT, "")
add("Admin", "Chats", "Send menu (WRITE)", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox/menu", curl_post("/api/admin/tenants/inbox/menu", f'{{"wa_id":"{WA}"}}'), SHOT, "")
add("Admin", "Chats", "Handover (WRITE)", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox/handover", curl_post("/api/admin/tenants/inbox/handover", f'{{"wa_id":"{WA}","mode":"human"}}'), SHOT, "")
add("Admin", "Chats", "Assign agent (WRITE)", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox/assign", curl_post("/api/admin/tenants/inbox/assign", f'{{"wa_id":"{WA}","agent_id":"agent1"}}'), SHOT, "")
add("Admin", "Chats", "Resolve (WRITE)", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox/resolve", curl_post("/api/admin/tenants/inbox/resolve", f'{{"wa_id":"{WA}","reply":true}}'), SHOT, "")
add("Admin", "Chats", "Attach file (WRITE)", "admin (view_inbox)", "POST", "/api/admin/tenants/inbox/attach", curl_multipart("/api/admin/tenants/inbox/attach", f'-F "wa_id={WA}" -F "file=@./sample.png"'), SHOT, "multipart")
add("Admin", "Chats", "Live events SSE", "admin (view_inbox)", "GET", "/api/admin/tenants/inbox/events", curl_get("/api/admin/tenants/inbox/events"), SHOT, "GET required for EventSource")

# Profile — admin EDIT
add("Admin", "Profile", "Load detail (READ)", "admin", "POST", f"/api/admin/tenants/{TID}/detail", curl_post(f"/api/admin/tenants/{TID}/detail"), SHOT, "#/tenants/:id/profile")
add(
    "Admin",
    "Profile",
    "Save draft (EDIT)",
    "admin (manage_operations)",
    "POST",
    f"/api/admin/tenants/{TID}/profile",
    curl_post(
        f"/api/admin/tenants/{TID}/profile",
        '{"brand":{"name":"Wanderly Bot","tagline":"Software that ships","support_email":"support@wanderly.test"}}',
    ),
    SHOT,
    "Admin can edit — SA cannot (view-only)",
)
add(
    "Admin",
    "Profile",
    "Publish / queue approval (EDIT)",
    "admin (manage_operations)",
    "POST",
    f"/api/admin/tenants/{TID}/publish",
    curl_post(f"/api/admin/tenants/{TID}/publish"),
    SHOT,
    "Admin publish → pending_approval for SA to approve",
)
add(
    "Admin",
    "Profile",
    "Submit change request",
    "admin",
    "POST",
    "/api/tenant-change-requests",
    curl_post(
        "/api/tenant-change-requests",
        f'{{"request_type":"publish_profile","tenant_id":"{TID}","note":""}}',
    ),
    SHOT,
    "Admin submits; SA approves on Business requests",
)
add(
    "Admin",
    "Profile",
    "My change requests",
    "admin",
    "POST",
    "/api/tenant-change-requests/mine",
    curl_post("/api/tenant-change-requests/mine"),
    SHOT,
    "",
)

# WhatsApp menu — admin EDIT
add("Admin", "WhatsApp menu", "Load resolved menu (READ)", "admin", "POST", "/api/admin/tenants/resolved", curl_post("/api/admin/tenants/resolved"), SHOT, "#/tenants/:id/menu")
add(
    "Admin",
    "WhatsApp menu",
    "Save intent (EDIT)",
    "admin (manage_operations)",
    "POST",
    f"/api/admin/tenants/{TID}/intents/{{name}}",
    curl_post(f"/api/admin/tenants/{TID}/intents/faq", '{"enabled":true,"title":"FAQ"}'),
    SHOT,
    "SA cannot edit intents in view-only mode",
)
add(
    "Admin",
    "WhatsApp menu",
    "Save menu draft (EDIT)",
    "admin (manage_operations)",
    "POST",
    f"/api/admin/tenants/{TID}/profile",
    curl_post(f"/api/admin/tenants/{TID}/profile", '{"menu":{"greeting":"Hi! How can I help?"}}'),
    SHOT,
    "",
)
add(
    "Admin",
    "WhatsApp menu",
    "Publish menu (EDIT)",
    "admin (manage_operations)",
    "POST",
    f"/api/admin/tenants/{TID}/publish",
    curl_post(f"/api/admin/tenants/{TID}/publish"),
    SHOT,
    "Queues for SA approval",
)
add(
    "Admin",
    "Profile menu",
    "Save hours/notifications (EDIT)",
    "admin (manage_operations)",
    "POST",
    f"/api/admin/tenants/{TID}/profile",
    curl_post(
        f"/api/admin/tenants/{TID}/profile",
        '{"hours":{"timezone":"Asia/Kolkata","always_open":true},"notifications":{"sales_email":"sales@wanderly.test"}}',
    ),
    SHOT,
    "#/tenants/:id/profile-menu",
)
add("Admin", "WhatsApp Settings", "List knowledge gaps", "admin", "POST", "/api/admin/tenants/knowledge-gaps", curl_post("/api/admin/tenants/knowledge-gaps"), SHOT, "#/tenants/:id/settings")
add("Admin", "WhatsApp Settings", "Resolve gap (EDIT)", "admin", "POST", "/api/admin/tenants/knowledge-gaps/resolve", curl_post("/api/admin/tenants/knowledge-gaps/resolve", '{"id":1}'), SHOT, "")
add("Admin", "WhatsApp Settings", "Create FAQ from gap (EDIT)", "admin", "POST", "/api/admin/tenants/knowledge-gaps/create-faq", curl_post("/api/admin/tenants/knowledge-gaps/create-faq", '{"question":"Q","answer":"A"}'), SHOT, "Live — bypasses approval")

# Website crawler — admin WRITE
add("Admin", "Website crawler", "List runs", "admin", "POST", "/api/admin/tenants/crawl-runs", curl_post("/api/admin/tenants/crawl-runs"), SHOT, "#/tenants/:id/website-crawler")
add("Admin", "Website crawler", "Start crawl (WRITE)", "admin", "POST", "/api/admin/tenants/crawl", curl_post("/api/admin/tenants/crawl", '{"url":"https://example.com","max_pages":20}'), SHOT, "")
add("Admin", "Website crawler", "Staged pages", "admin", "POST", "/api/admin/tenants/crawl-runs/staged", curl_post("/api/admin/tenants/crawl-runs/staged", '{"run_id":1}'), SHOT, "")
add("Admin", "Website crawler", "Approve run (WRITE)", "admin", "POST", "/api/admin/tenants/crawl-runs/approve", curl_post("/api/admin/tenants/crawl-runs/approve", '{"run_id":1}'), SHOT, "")
add("Admin", "Website crawler", "Reject run (WRITE)", "admin", "POST", "/api/admin/tenants/crawl-runs/reject", curl_post("/api/admin/tenants/crawl-runs/reject", '{"run_id":1}'), SHOT, "")
add("Admin", "Website crawler", "List files", "admin", "POST", "/api/admin/tenants/files", curl_post("/api/admin/tenants/files"), SHOT, "")
add("Admin", "Website crawler", "Upload file (WRITE)", "admin", "POST", "/api/admin/tenants/files/upload", curl_multipart("/api/admin/tenants/files/upload", '-F "file=@./doc.pdf"'), SHOT, "multipart")
add("Admin", "Website crawler", "Delete file (WRITE)", "admin", "POST", "/api/admin/tenants/files/delete", curl_post("/api/admin/tenants/files/delete", '{"file_id":1}'), SHOT, "")
add("Admin", "Website crawler", "Preview file", "admin", "POST", "/api/admin/tenants/files/preview", curl_post("/api/admin/tenants/files/preview", '{"file_id":1}'), SHOT, "")
add("Admin", "Website crawler", "Download file", "admin", "POST", "/api/admin/tenants/files/download", curl_post("/api/admin/tenants/files/download", '{"file_id":1}'), SHOT, "")
add("Admin", "Website crawler", "Bifurcate existing (WRITE)", "admin", "POST", "/api/admin/tenants/files/bifurcate-existing", curl_post("/api/admin/tenants/files/bifurcate-existing", '{"file_id":1}'), SHOT, "")

# Customers — admin
add("Admin", "Customers", "List customers", "admin (view_customers)", "POST", "/api/admin/tenants/customers", curl_post("/api/admin/tenants/customers", '{"limit":50,"q":""}'), SHOT, "#/tenants/:id/customers")
add("Admin", "Customers", "Export CSV", "admin (view_customers)", "POST", "/api/admin/tenants/customers/export", curl_post("/api/admin/tenants/customers/export"), SHOT, "blob")

# ═══════════════════════════════════════════════════════════════════════════
# SUPERADMIN — same 6 pages but READ / VIEW-ONLY (cannot edit)
# ═══════════════════════════════════════════════════════════════════════════
add(
    "Superadmin",
    "Dashboard",
    "Overview (READ)",
    "super_admin",
    "POST",
    "/api/admin/tenants/send2-credentials/status",
    curl_post("/api/admin/tenants/send2-credentials/status"),
    SHOT,
    "View-only inside tenant — same sidebar as admin",
)
add("Superadmin", "Dashboard", "Inbox preview (READ)", "super_admin", "POST", "/api/admin/tenants/inbox", curl_post("/api/admin/tenants/inbox", '{"include_resolved":false}'), SHOT, "")
add("Superadmin", "Dashboard", "Chat history (READ)", "super_admin", "POST", "/api/admin/tenants/chat-history", curl_post("/api/admin/tenants/chat-history", '{"days":1,"limit":500}'), SHOT, "")
add("Superadmin", "Dashboard", "Crawl runs (READ)", "super_admin", "POST", "/api/admin/tenants/crawl-runs", curl_post("/api/admin/tenants/crawl-runs"), SHOT, "")
add("Superadmin", "Dashboard", "Customers preview (READ)", "super_admin", "POST", "/api/admin/tenants/customers", curl_post("/api/admin/tenants/customers", '{"limit":50}'), SHOT, "")
add("Superadmin", "Dashboard", "Errors strip (READ)", "super_admin", "POST", "/api/admin/errors", curl_post("/api/admin/errors", "{}", f"?limit=100&tenant_id={TID}"), SHOT, "")
add(
    "Superadmin",
    "Dashboard",
    "Resync Send2 credentials",
    "super_admin",
    "POST",
    f"/api/admin/tenants/{TID}/send2-credentials/resync",
    curl_post(f"/api/admin/tenants/{TID}/send2-credentials/resync"),
    SHOT,
    "SA-only action",
)

add("Superadmin", "Chats", "Inbox list (READ)", "super_admin", "POST", "/api/admin/tenants/inbox", curl_post("/api/admin/tenants/inbox", '{"include_resolved":true}'), SHOT, "View-only — no reply/edit without support Login")
add("Superadmin", "Chats", "Conversations (READ)", "super_admin", "POST", "/api/admin/tenants/conversations", curl_post("/api/admin/tenants/conversations", '{"limit":500}'), SHOT, "")
add("Superadmin", "Chats", "Load thread (READ)", "super_admin", "POST", "/api/admin/tenants/chat/thread", curl_post("/api/admin/tenants/chat/thread", f'{{"wa_id":"{WA}","limit":300}}'), SHOT, "")
add("Superadmin", "Chats", "Agents (READ)", "super_admin", "POST", "/api/admin/tenants/agents", curl_post("/api/admin/tenants/agents"), SHOT, "")
add("Superadmin", "Chats", "Live events SSE (READ)", "super_admin", "GET", "/api/admin/tenants/inbox/events", curl_get("/api/admin/tenants/inbox/events"), SHOT, "")

add(
    "Superadmin",
    "Profile",
    "Load detail (READ only — cannot edit)",
    "super_admin",
    "POST",
    f"/api/admin/tenants/{TID}/detail",
    curl_post(f"/api/admin/tenants/{TID}/detail"),
    SHOT,
    "UI shows View-only banner; profile save/publish blocked",
)
add(
    "Superadmin",
    "Profile",
    "Resolved profile (READ)",
    "super_admin",
    "POST",
    "/api/admin/tenants/resolved",
    curl_post("/api/admin/tenants/resolved"),
    SHOT,
    "Do NOT call /profile or /publish as SA without support Login",
)

add("Superadmin", "WhatsApp menu", "Load menu (READ only)", "super_admin", "POST", "/api/admin/tenants/resolved", curl_post("/api/admin/tenants/resolved"), SHOT, "Cannot save intents / publish")
add("Superadmin", "WhatsApp Settings", "List knowledge gaps (READ)", "super_admin", "POST", "/api/admin/tenants/knowledge-gaps", curl_post("/api/admin/tenants/knowledge-gaps"), SHOT, "")
add("Superadmin", "Website crawler", "List runs (READ)", "super_admin", "POST", "/api/admin/tenants/crawl-runs", curl_post("/api/admin/tenants/crawl-runs"), SHOT, "")
add("Superadmin", "Website crawler", "Staged pages (READ)", "super_admin", "POST", "/api/admin/tenants/crawl-runs/staged", curl_post("/api/admin/tenants/crawl-runs/staged", '{"run_id":1}'), SHOT, "")
add("Superadmin", "Website crawler", "List files (READ)", "super_admin", "POST", "/api/admin/tenants/files", curl_post("/api/admin/tenants/files"), SHOT, "")
add("Superadmin", "Customers", "List customers (READ)", "super_admin", "POST", "/api/admin/tenants/customers", curl_post("/api/admin/tenants/customers", '{"limit":50,"q":""}'), SHOT, "")
add("Superadmin", "Customers", "Export CSV (READ)", "super_admin", "POST", "/api/admin/tenants/customers/export", curl_post("/api/admin/tenants/customers/export"), SHOT, "")

# ═══════════════════════════════════════════════════════════════════════════
# SUPERADMIN EXTRA — Manage (not on admin sidebar)
# ═══════════════════════════════════════════════════════════════════════════

# People / privileges
add("Superadmin (extra)", "People / privileges", "List admins", "super_admin", "POST", "/api/auth/admins", curl_post("/api/auth/admins"), SHOT_SA, "#/team")
add(
    "Superadmin (extra)",
    "People / privileges",
    "Create admin",
    "super_admin",
    "POST",
    "/api/auth/create",
    curl_post("/api/auth/create", f'{{"username":"newadmin","password":"ChangeMe1!","role":"admin","tenant_id":"{TID}"}}'),
    SHOT_SA,
    "",
)
add(
    "Superadmin (extra)",
    "People / privileges",
    "Update permissions",
    "super_admin",
    "POST",
    "/api/auth/admins/{username}/update",
    curl_post("/api/auth/admins/newadmin/update", '{"permissions":{"view_inbox":true,"view_customers":true}}'),
    SHOT_SA,
    "",
)
add(
    "Superadmin (extra)",
    "People / privileges",
    "Reset password",
    "super_admin",
    "POST",
    "/api/auth/admins/{username}/reset-password",
    curl_post("/api/auth/admins/newadmin/reset-password", '{"new_password":"ChangeMe2!"}'),
    SHOT_SA,
    "",
)
add(
    "Superadmin (extra)",
    "People / privileges",
    "Delete admin",
    "super_admin",
    "POST",
    "/api/auth/admins/{username}/delete",
    curl_post("/api/auth/admins/newadmin/delete"),
    SHOT_SA,
    "",
)

# Business requests — SA APPROVES, does not edit tenant
add(
    "Superadmin (extra)",
    "Business requests",
    "List pending edit requests (APPROVE queue)",
    "super_admin",
    "POST",
    "/api/admin/tenant-change-requests",
    curl_post("/api/admin/tenant-change-requests", '{"status":"pending"}'),
    SHOT_SA,
    "SA reviews admin publish/edit requests — cannot edit profile directly",
)
add(
    "Superadmin (extra)",
    "Business requests",
    "Approve edit request",
    "super_admin",
    "POST",
    "/api/admin/tenant-change-requests/{id}/decision",
    curl_post("/api/admin/tenant-change-requests/22/decision", '{"decision":"approved","note":""}'),
    SHOT_SA,
    "Applies admin's pending profile publish",
)
add(
    "Superadmin (extra)",
    "Business requests",
    "Reject edit request",
    "super_admin",
    "POST",
    "/api/admin/tenant-change-requests/{id}/decision",
    curl_post("/api/admin/tenant-change-requests/22/decision", '{"decision":"rejected","note":"fix missing"}'),
    SHOT_SA,
    "",
)

# Activity log
add(
    "Superadmin (extra)",
    "Activity log",
    "List events",
    "super_admin",
    "POST",
    "/api/admin/audit-history",
    curl_post(
        "/api/admin/audit-history",
        f'{{"limit":50,"offset":0,"sort_by":"created_at","sort_order":"desc","start_date":"2026-11-19","end_date":"2026-11-25","tenant_id":"{TID}"}}',
    ),
    SHOT_SA,
    "#/audit-history",
)
add(
    "Superadmin (extra)",
    "Activity log",
    "Statistics",
    "super_admin",
    "POST",
    "/api/admin/audit-statistics",
    curl_post(
        "/api/admin/audit-statistics",
        f'{{"start_date":"2026-11-19","end_date":"2026-11-25","tenant_id":"{TID}"}}',
    ),
    SHOT_SA,
    "",
)
add(
    "Superadmin (extra)",
    "Activity log",
    "Export",
    "super_admin",
    "POST",
    "/api/admin/audit-export",
    curl_post("/api/admin/audit-export", f'{{"format":"csv","tenant_id":"{TID}"}}'),
    SHOT_SA,
    "",
)

# Errors & health
add(
    "Superadmin (extra)",
    "Errors & health",
    "List errors",
    "super_admin",
    "POST",
    "/api/admin/errors",
    curl_post("/api/admin/errors", "{}", f"?limit=50&offset=0&tenant_id={TID}"),
    SHOT_SA,
    "#/errors",
)

# Privilege summary rows
add(
    "README",
    "Privilege difference",
    "Admin can EDIT",
    "admin",
    "n/a",
    "profile / intents / publish / crawl / chats write",
    "n/a",
    SHOT,
    "Admin edits → publish queues Business request for SA",
)
add(
    "README",
    "Privilege difference",
    "Superadmin can APPROVE only (not edit)",
    "super_admin",
    "n/a",
    "/api/admin/tenant-change-requests/{id}/decision",
    "n/a",
    SHOT_SA,
    "View-only on Profile/WhatsApp; approve/reject on Business requests",
)

# Remap admin page rows to captured localhost screenshots
PAGE_SHOT = {
    "Login": SHOT_LOGIN,
    "Dashboard": SHOT_DASH,
    "Chats": SHOT_CHATS,
    "Profile": SHOT_PROFILE,
    "WhatsApp menu": SHOT_WA_MENU,
    "Profile menu": SHOT_PROF_MENU,
    "WhatsApp Settings": SHOT_WA_SET,
    "Website crawler": SHOT_CRAWL,
    "Customers": SHOT_CUST,
    "Tenant bootstrap": SHOT_DASH,
}
for r in rows:
    if r["page_type"] in ("Admin", "Auth", "Shared (admin + superadmin)", "Superadmin"):
        mapped = PAGE_SHOT.get(r["page"])
        if mapped:
            r["screenshot"] = mapped

# ── Write ───────────────────────────────────────────────────────────────────
out = Path(__file__).resolve().parents[1] / "admin-superadmin-apis-curls.csv"
fields = [
    "page_type",
    "page",
    "subpage",
    "roles",
    "http_method",
    "api_path",
    "curl",
    "date_made",
    "who_made",
    "date_combined",
    "who_combined",
    "screenshot",
    "notes",
]
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

by_type: dict[str, int] = {}
for r in rows:
    by_type[r["page_type"]] = by_type.get(r["page_type"], 0) + 1

print(f"Wrote {len(rows)} rows -> {out}")
for k, v in sorted(by_type.items()):
    print(f"  {k}: {v}")
