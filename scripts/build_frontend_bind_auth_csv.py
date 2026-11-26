"""Generate frontend-bind CSV for signup / privileges / onboarding APIs."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend-bind-auth-apis.csv"

ROWS = [
    {
        "flow_order": 1,
        "ui_screen": "Send2 / External signup (no panel login)",
        "api_name": "Signup",
        "what_it_does": (
            "Creates/updates company admin from Send2: stores plain username, "
            "admins.id from request id, hashed + vault password, auto-creates "
            "unique short tenant_id (or reuses existing for same admins.id; "
            "optional tenant_id links second admin to same company). Returns session_id. "
            "Public endpoint — no auth headers."
        ),
        "http_method": "POST",
        "url": "http://localhost:9000/api/auth/signup",
        "auth_required": "No (public)",
        "auth_headers": "",
        "who_can_call": "Send2Digital / public integrator",
        "request_body_json": (
            '{"username":"japan","id":"12234","password":"dshjksjhsbhjsli"}'
        ),
        "optional_body_fields": (
            "tenant_id (string) — pass existing tenant_id to attach second admin "
            "to same company; omit to auto-create new tenant_id"
        ),
        "request_field_details": (
            "username (string, plain, required) | "
            "id (string/number, required) = chatbot admins.id PK e.g. 12234 | "
            "password (string, required) | tenant_id (string, optional)"
        ),
        "success_status": "200",
        "success_response_json": (
            '{"status":"ok","action":"created|updated","user_id":12234,"id":12234,'
            '"username":"japan","tenant_id":"a1b2c3d4e5f6","session_id":"<token>",'
            '"role":"admin","send2_validated":false}'
        ),
        "error_codes": "400 invalid input / duplicate username | 502 signup failed",
        "frontend_bind_notes": (
            "Not called from admin panel UI normally. After signup store returned "
            "id + session_id + tenant_id. Admin later authenticates with "
            "username + session_id headers. onboarding_approved stays false until "
            "first-login/complete publishes profile v1."
        ),
        "curl": (
            "curl --location 'http://localhost:9000/api/auth/signup' "
            "--header 'Content-Type: application/json' "
            "--data '{\"username\":\"japan\",\"id\":\"12234\",\"password\":\"dshjksjhsbhjsli\"}'"
        ),
    },
    {
        "flow_order": 2,
        "ui_screen": "Privileges panel — user dropdown",
        "api_name": "Menu privileges users (dropdown)",
        "what_it_does": (
            "Lists all admin + sub_admin accounts for the privileges dropdown "
            "(id + username + role + tenant_id). Superadmin only."
        ),
        "http_method": "POST",
        "url": "http://localhost:9000/api/auth/menu-privileges/users",
        "auth_required": "Yes",
        "auth_headers": "username: Customercare | session_id: <live session>",
        "who_can_call": "super_admin (e.g. Customercare / id 3042)",
        "request_body_json": "{}",
        "optional_body_fields": "",
        "request_field_details": (
            "No body fields required. Auth only via headers username + session_id."
        ),
        "success_status": "200",
        "success_response_json": (
            '{"ok":true,"count":N,"users":[{"id":3518,"user_id":3518,'
            '"username":"spiritual","role":"admin","tenant_id":"spiritual","email":null}]}'
        ),
        "error_codes": "401 invalid credentials | 403 not super_admin",
        "frontend_bind_notes": (
            "Bind dropdown options to users[]. Display label: username (id). "
            "On select, store selected id and call menu-privileges/get. "
            "Helper: menuPrivilegesApi.users()"
        ),
        "curl": (
            "curl --location 'http://localhost:9000/api/auth/menu-privileges/users' "
            "--header 'Content-Type: application/json' "
            "--header 'username: Customercare' "
            "--header 'session_id: 3042_1794914340_c8f3a72d9e6b' "
            "--data '{}'"
        ),
    },
    {
        "flow_order": 3,
        "ui_screen": "Privileges panel — load checkboxes after dropdown select",
        "api_name": "Menu privileges get",
        "what_it_does": (
            "Returns selected user's menu privileges as active/inactive map + "
            "items[] for checkbox UI. Superadmin target is read-only "
            "(all active, editable=false)."
        ),
        "http_method": "POST",
        "url": "http://localhost:9000/api/auth/menu-privileges/get",
        "auth_required": "Yes",
        "auth_headers": "username: Customercare | session_id: <live session>",
        "who_can_call": "super_admin",
        "request_body_json": '{"id":3518}',
        "optional_body_fields": "user_id — alias of id",
        "request_field_details": (
            "id (int, required) = admins.id of selected dropdown user | "
            "user_id (int, optional alias)"
        ),
        "success_status": "200",
        "success_response_json": (
            '{"ok":true,"id":3518,"user_id":3518,"username":"spiritual","role":"admin",'
            '"skip_grant_check":false,"editable":true,'
            '"menu_ids":["graphic","chats"],'
            '"privileges":{"graphic":true,"chats":true,"profile":false,"customer":false,'
            '"website_crawler":false,"setup_chatbot":false,"menu":false},'
            '"items":[{"key":"graphic","active":true},{"key":"chats","active":true},'
            '{"key":"profile","active":false}]}'
        ),
        "error_codes": "400 id required/invalid | 401 | 403 | 404 admin not found",
        "frontend_bind_notes": (
            "Privilege keys: graphic, chats, profile, customer, website_crawler, "
            "setup_chatbot, menu. Prefer privileges{} or items[].active for checkboxes. "
            "If editable===false do not allow Save. Nav mapping: graphic→overview, "
            "chats→inbox, profile→profile, customer→customers, "
            "website_crawler→website-crawler/uploads, setup_chatbot→profile-menu/settings, "
            "menu→menu. Helper: menuPrivilegesApi.get({id})"
        ),
        "curl": (
            "curl --location 'http://localhost:9000/api/auth/menu-privileges/get' "
            "--header 'Content-Type: application/json' "
            "--header 'username: Customercare' "
            "--header 'session_id: 3042_1794914340_c8f3a72d9e6b' "
            "--data '{\"id\":3518}'"
        ),
    },
    {
        "flow_order": 4,
        "ui_screen": "Privileges panel — Save button",
        "api_name": "Menu privileges save",
        "what_it_does": (
            "Saves active/inactive menu grants for selected admin/sub_admin. "
            "Cannot save for superadmin (always full menus)."
        ),
        "http_method": "POST",
        "url": "http://localhost:9000/api/auth/menu-privileges/save",
        "auth_required": "Yes",
        "auth_headers": "username: Customercare | session_id: <live session>",
        "who_can_call": "super_admin",
        "request_body_json": (
            '{"id":3518,"privileges":{"graphic":true,"chats":true,"profile":false,'
            '"customer":false,"website_crawler":false,"setup_chatbot":false,"menu":false}}'
        ),
        "optional_body_fields": (
            "user_id (alias of id) | menu_ids (string[]) alternative to privileges map | "
            "privileges_ids (int[]) catalog ids"
        ),
        "request_field_details": (
            "id (int, required) | privileges (object, preferred): keys "
            "graphic|chats|profile|customer|website_crawler|setup_chatbot|menu "
            "with boolean true=active"
        ),
        "success_status": "200",
        "success_response_json": (
            '{"ok":true,"id":3518,"user_id":3518,"username":"spiritual",'
            '"menu_ids":["graphic","chats"],'
            '"privileges":{"graphic":true,"chats":true,"profile":false,"customer":false,'
            '"website_crawler":false,"setup_chatbot":false,"menu":false},'
            '"items":[...],"grants":[...]}'
        ),
        "error_codes": "400 cannot save for superadmin / invalid target | 401 | 403 | 404",
        "frontend_bind_notes": (
            "Send checkbox state as privileges{}. true keys become grants. "
            "After save refresh get or use response.privileges. "
            "Helper: menuPrivilegesApi.save({id, privileges})"
        ),
        "curl": (
            "curl --location 'http://localhost:9000/api/auth/menu-privileges/save' "
            "--header 'Content-Type: application/json' "
            "--header 'username: Customercare' "
            "--header 'session_id: 3042_1794914340_c8f3a72d9e6b' "
            "--data '{\"id\":3518,\"privileges\":{\"graphic\":true,\"chats\":true,"
            "\"profile\":false,\"customer\":false,\"website_crawler\":false,"
            "\"setup_chatbot\":false,\"menu\":false}}'"
        ),
    },
    {
        "flow_order": 5,
        "ui_screen": "Superadmin — Onboarded users page",
        "api_name": "Onboarding users list",
        "what_it_does": (
            "Lists all company admin + sub_admin users for customer_care "
            "onboarded-users view (tenant_id + onboarding_approved). "
            "Used for login-as / support access list."
        ),
        "http_method": "POST",
        "url": "http://localhost:9000/api/auth/onboarding-users",
        "auth_required": "Yes",
        "auth_headers": "username: Customercare | session_id: <live session>",
        "who_can_call": "customer_care / Customercare (require_customer_care)",
        "request_body_json": "{}",
        "optional_body_fields": "",
        "request_field_details": "Empty JSON body. Auth via headers only.",
        "success_status": "200",
        "success_response_json": (
            '{"count":N,"users":[{"id":12234,"username":"japan","email":null,'
            '"role":"admin","tenant_id":"a1b2c3d4e5f6","created_at":"...",'
            '"onboarding_approved":true}]}'
        ),
        "error_codes": "401 | 403 not customer_care",
        "frontend_bind_notes": (
            "Table columns: username, role, tenant_id, onboarding_approved "
            "(Approved/Pending), created_at. onboarding_approved=true only after "
            "Set up chatbot published profile v1 (not merely having tenant_id). "
            "Helper: adminsApi.onboardingUsers()"
        ),
        "curl": (
            "curl --location 'http://localhost:9000/api/auth/onboarding-users' "
            "--header 'Content-Type: application/json' "
            "--header 'username: Customercare' "
            "--header 'session_id: 3042_1794914340_c8f3a72d9e6b' "
            "--data '{}'"
        ),
    },
    {
        "flow_order": 6,
        "ui_screen": "Company admin — Set up chatbot wizard (Finish)",
        "api_name": "First-login complete / Set up chatbot",
        "what_it_does": (
            "Finishes onboarding for logged-in company admin. tenant_id is taken "
            "from authenticated admin (username+session_id) — do NOT send tenant_id "
            "in body. Sets WhatsApp phone, company/brand snapshot, publishes "
            "profile v1, unlocks console (onboarding_approved=true)."
        ),
        "http_method": "POST",
        "url": "http://localhost:9000/api/auth/first-login/complete",
        "auth_required": "Yes",
        "auth_headers": (
            "username: japan | session_id: <that admin live session from signup/login>"
        ),
        "who_can_call": (
            "role=admin with signup tenant_id and unpublished profile (version 0)"
        ),
        "request_body_json": (
            '{"waba_phone_id":"+919876543210","mobile_number":"+919876543210",'
            '"snapshot":{"vertical":"generic","display_name":"Japan Co",'
            '"brand":{"name":"Japan Co","bot_name":"Asha","tagline":"Here to help",'
            '"support_email":"support@example.com","support_phone":"+919876543210"}}}'
        ),
        "optional_body_fields": (
            "files ([{filename, content base64}]) | lane (kit|any) | "
            "upload_draft (staged bifurcation object)"
        ),
        "request_field_details": (
            "waba_phone_id (string) | mobile_number (string, country code + digits) | "
            "snapshot.vertical | snapshot.display_name | "
            "snapshot.brand.name|bot_name|tagline|support_email|support_phone. "
            "tenant_id NOT in body."
        ),
        "success_status": "200",
        "success_response_json": (
            '{"ok":true,"tenant_id":"<from session>","version":1,"vertical":"generic",'
            '"username":"japan","onboarding_approved":true,"tenant":{...},'
            '"upload":{"status":"published|failed"} optional}'
        ),
        "error_codes": (
            "400 no tenant on admin | 401 | 403 not company admin | "
            "409 already published | 422 phone/profile validation | 404 tenant missing"
        ),
        "frontend_bind_notes": (
            "Call on Finish setup only. Prefill wizard from /api/auth/me (tenant_id). "
            "After 200: refreshIdentity() then navigate to "
            "/tenants/{tenant_id}/overview. Do not pass tenant_id in JSON. "
            "Helper: adminsApi.firstLoginComplete({waba_phone_id, mobile_number, snapshot})"
        ),
        "curl": (
            "curl --location 'http://localhost:9000/api/auth/first-login/complete' "
            "--header 'Content-Type: application/json' "
            "--header 'username: japan' "
            "--header 'session_id: b4lLGk7cQ4hFZMHM5AwG7ig7vcV_Y3WnZ6tA-ZX5kFk' "
            "--data-raw '{\"waba_phone_id\":\"+919876543210\","
            "\"mobile_number\":\"+919876543210\","
            "\"snapshot\":{\"vertical\":\"generic\",\"display_name\":\"Japan Co\","
            "\"brand\":{\"name\":\"Japan Co\",\"bot_name\":\"Asha\","
            "\"tagline\":\"Here to help\",\"support_email\":\"support@example.com\","
            "\"support_phone\":\"+919876543210\"}}}'"
        ),
    },
]

FIELDS = [
    "flow_order",
    "ui_screen",
    "api_name",
    "what_it_does",
    "http_method",
    "url",
    "auth_required",
    "auth_headers",
    "who_can_call",
    "request_body_json",
    "optional_body_fields",
    "request_field_details",
    "success_status",
    "success_response_json",
    "error_codes",
    "frontend_bind_notes",
    "curl",
]


def main() -> None:
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(ROWS)
    print(f"Wrote {len(ROWS)} rows -> {OUT}")


if __name__ == "__main__":
    main()
