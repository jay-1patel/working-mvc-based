"""Generate one Postman collection JSON file per admin API."""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent / "requests"
BASE = "{{base_url}}"
AUTH_HEADERS = [
    {"key": "Content-Type", "value": "application/json"},
    {"key": "username", "value": "{{username}}"},
    {"key": "session_id", "value": "{{session_id}}"},
]
VARS = [
    {"key": "base_url", "value": "http://127.0.0.1:9000"},
    {"key": "username", "value": "cars"},
    {"key": "session_id", "value": "cars-static-session"},
    {"key": "wa_id", "value": "919876543210"},
    {"key": "ticket_id", "value": "TKT-DUMMY-001"},
    {"key": "tenant_id", "value": "c"},
    {"key": "run_id", "value": "1"},
    {"key": "filename", "value": "sample.pdf"},
    {"key": "gap_id", "value": "1"},
    {"key": "agent_id", "value": "cars"},
]


def slug(method: str, path: str) -> str:
    clean = path.strip("/").replace("/", "__")
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", clean)
    return f"{method.upper()}__{clean}"


def make_collection(name: str, method: str, path: str, body: dict | None, headers: list | None = None) -> dict:
    hdrs = headers if headers is not None else (AUTH_HEADERS if method.upper() != "GET" or True else AUTH_HEADERS)
    # Always send session headers except pure anonymous login/status
    req: dict = {
        "method": method.upper(),
        "header": hdrs,
        "url": f"{BASE}{path}",
    }
    if body is not None:
        req["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    return {
        "info": {
            "name": name,
            "description": f"{method.upper()} {path}",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": VARS,
        "item": [{"name": name, "request": req}],
    }


# (filename stem override or None, name, method, path, body, headers|None)
APIS: list[tuple] = [
    # Auth
    ("01_auth_status", "Auth status", "GET", "/api/auth/status", None, []),
    (
        "02_auth_login",
        "Auth login",
        "POST",
        "/api/auth/login",
        {"username": "{{username}}", "session_id": "{{session_id}}"},
        [{"key": "Content-Type", "value": "application/json"}],
    ),
    ("03_auth_me", "Auth me", "GET", "/api/auth/me", None, AUTH_HEADERS[1:]),
    ("04_auth_admins", "Auth admins", "GET", "/api/auth/admins", None, AUTH_HEADERS[1:]),
    # Inbox chat screen
    (
        "05_inbox",
        "Inbox queue",
        "POST",
        "/api/admin/tenants/inbox",
        {"include_resolved": False},
        None,
    ),
    (
        "06_conversations_detail",
        "Conversation detail",
        "POST",
        "/api/admin/tenants/conversations/detail",
        {"wa_id": "{{wa_id}}", "limit": 300},
        None,
    ),
    (
        "07_chat_history",
        "Chat history",
        "POST",
        "/api/admin/tenants/chat-history",
        {"days": 30, "wa_id": "{{wa_id}}", "limit": 500},
        None,
    ),
    ("08_agents", "Agents list", "POST", "/api/admin/tenants/agents", {}, None),
    (
        "09_inbox_assign",
        "Inbox assign",
        "POST",
        "/api/admin/tenants/inbox/assign",
        {"wa_id": "{{wa_id}}", "agent_id": "{{agent_id}}"},
        None,
    ),
    (
        "10_inbox_handover_bot",
        "Inbox handover bot",
        "POST",
        "/api/admin/tenants/inbox/handover",
        {"wa_id": "{{wa_id}}", "mode": "bot"},
        None,
    ),
    (
        "11_inbox_handover_human",
        "Inbox handover human",
        "POST",
        "/api/admin/tenants/inbox/handover",
        {"wa_id": "{{wa_id}}", "mode": "human"},
        None,
    ),
    (
        "12_inbox_reply",
        "Inbox reply",
        "POST",
        "/api/admin/tenants/inbox/reply",
        {"wa_id": "{{wa_id}}", "message": "Hello from Postman"},
        None,
    ),
    (
        "13_inbox_attach",
        "Inbox attach",
        "POST",
        "/api/admin/tenants/inbox/attach",
        {
            "filename": "note.txt",
            "content": "SGVsbG8gZnJvbSBQb3N0bWFu",
            "media_type": "text/plain",
        },
        None,
    ),
    (
        "14_inbox_resolve",
        "Inbox resolve",
        "POST",
        "/api/admin/tenants/inbox/resolve",
        {"wa_id": "{{wa_id}}", "reply": True},
        None,
    ),
    # Customers / complaints
    (
        "15_customers",
        "Customers list",
        "POST",
        "/api/admin/tenants/customers",
        {"q": "", "limit": 200},
        None,
    ),
    (
        "16_customers_export",
        "Customers export",
        "POST",
        "/api/admin/tenants/customers/export",
        {"format": "csv"},
        None,
    ),
    (
        "17_complaints",
        "Complaints list",
        "POST",
        "/api/admin/tenants/complaints",
        {"status": None, "limit": 200},
        None,
    ),
    (
        "18_complaints_update",
        "Complaints update",
        "POST",
        "/api/admin/tenants/complaints/update",
        {
            "ticket_id": "{{ticket_id}}",
            "status": "in_progress",
            "priority": "high",
            "assigned_to": "cars",
        },
        None,
    ),
    (
        "19_complaints_reply",
        "Complaints reply",
        "POST",
        "/api/admin/tenants/complaints/reply",
        {
            "ticket_id": "{{ticket_id}}",
            "message": "We are checking this",
            "status": "in_progress",
        },
        None,
    ),
    (
        "20_complaints_delete",
        "Complaints delete",
        "POST",
        "/api/admin/tenants/complaints/delete",
        {"ticket_id": "TKT-DUMMY-003"},
        None,
    ),
    # Resolved / crawl / files / gaps / kits
    ("21_resolved", "Resolved profile", "POST", "/api/admin/tenants/resolved", {}, None),
    (
        "22_crawl",
        "Crawl start",
        "POST",
        "/api/admin/tenants/crawl",
        {"url": "https://example.com", "max_depth": 2},
        None,
    ),
    (
        "23_crawl_runs",
        "Crawl runs",
        "POST",
        "/api/admin/tenants/crawl-runs",
        {"limit": 20},
        None,
    ),
    (
        "24_crawl_runs_staged",
        "Crawl staged",
        "POST",
        "/api/admin/tenants/crawl-runs/staged",
        {"run_id": "{{run_id}}"},
        None,
    ),
    (
        "25_crawl_runs_export",
        "Crawl export",
        "POST",
        "/api/admin/tenants/crawl-runs/export",
        {"run_id": "{{run_id}}", "format": "json"},
        None,
    ),
    (
        "26_crawl_runs_approve",
        "Crawl approve",
        "POST",
        "/api/admin/tenants/crawl-runs/approve",
        {"run_id": "{{run_id}}"},
        None,
    ),
    (
        "27_crawl_runs_reject",
        "Crawl reject",
        "POST",
        "/api/admin/tenants/crawl-runs/reject",
        {"run_id": "{{run_id}}"},
        None,
    ),
    ("28_files", "Files list", "POST", "/api/admin/tenants/files", {}, None),
    (
        "29_files_upload",
        "Files upload",
        "POST",
        "/api/admin/tenants/files/upload",
        {
            "filename": "postman-note.txt",
            "content": "SGVsbG8gZnJvbSBQb3N0bWFu",
            "module": "faq",
            "media_type": "text/plain",
        },
        None,
    ),
    (
        "30_files_bifurcate",
        "Files bifurcate",
        "POST",
        "/api/admin/tenants/files/bifurcate-existing",
        {"filenames": ["{{filename}}"], "auto_publish": False},
        None,
    ),
    (
        "31_files_preview",
        "Files preview",
        "POST",
        "/api/admin/tenants/files/preview",
        {"filename": "{{filename}}"},
        None,
    ),
    (
        "32_files_download",
        "Files download",
        "POST",
        "/api/admin/tenants/files/download",
        {"filename": "{{filename}}"},
        None,
    ),
    (
        "33_files_delete",
        "Files delete",
        "POST",
        "/api/admin/tenants/files/delete",
        {"filename": "postman-note.txt"},
        None,
    ),
    (
        "34_knowledge_gaps",
        "Knowledge gaps",
        "POST",
        "/api/admin/tenants/knowledge-gaps",
        {"resolved": False, "limit": 50},
        None,
    ),
    (
        "35_knowledge_gaps_resolve",
        "Knowledge gaps resolve",
        "POST",
        "/api/admin/tenants/knowledge-gaps/resolve",
        {"gap_id": "{{gap_id}}", "notes": "handled in Postman"},
        None,
    ),
    (
        "36_knowledge_gaps_create_faq",
        "Knowledge gaps create FAQ",
        "POST",
        "/api/admin/tenants/knowledge-gaps/create-faq",
        {"gap_id": "{{gap_id}}", "question": "Dummy Q?", "answer": "Dummy A"},
        None,
    ),
    (
        "37_onboarding_kits_list",
        "Onboarding kits list",
        "POST",
        "/api/admin/onboarding-kits/list",
        {},
        None,
    ),
    # Extra panel GETs used by UI
    (
        "38_dashboard_stats",
        "Dashboard stats",
        "GET",
        "/api/admin/dashboard/stats",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "39_analytics_overview",
        "Analytics overview",
        "GET",
        "/api/admin/analytics/overview?days=7",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "40_tenants_list",
        "Tenants list",
        "GET",
        "/api/admin/tenants",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "41_tenant_detail",
        "Tenant detail",
        "GET",
        "/api/admin/tenants/{{tenant_id}}/detail",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "42_tenant_orders",
        "Tenant orders",
        "GET",
        "/api/admin/tenants/{{tenant_id}}/orders",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "43_tenant_orders_stats",
        "Tenant orders stats",
        "GET",
        "/api/admin/tenants/{{tenant_id}}/orders/stats",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "44_callbacks",
        "Callbacks list",
        "GET",
        "/api/tenants/{{tenant_id}}/callbacks",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "45_offerings",
        "Offerings list",
        "GET",
        "/api/admin/tenants/{{tenant_id}}/offerings",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "46_errors",
        "API errors",
        "GET",
        "/api/admin/errors?limit=50&tenant_id={{tenant_id}}",
        None,
        AUTH_HEADERS[1:],
    ),
    (
        "47_audit_history",
        "Audit history",
        "GET",
        "/api/admin/audit-history?limit=50",
        None,
        AUTH_HEADERS[1:],
    ),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for existing in OUT.glob("*.json"):
        existing.unlink()

    index = []
    for stem, name, method, path, body, headers in APIS:
        # Fix run_id / gap_id to be numbers in JSON when possible — Postman vars stay quoted.
        # Keep as-is; Postman substitutes before send.
        coll = make_collection(name, method, path, body, headers)
        # For numeric vars inside JSON body strings like "{{run_id}}", Postman still works as string;
        # rewrite known numeric placeholders without quotes in raw JSON for crawl/gaps.
        if body is not None and any(k in body for k in ("run_id", "gap_id")):
            raw = json.dumps(body, indent=2)
            raw = raw.replace('"{{run_id}}"', "{{run_id}}")
            raw = raw.replace('"{{gap_id}}"', "{{gap_id}}")
            coll["item"][0]["request"]["body"]["raw"] = raw

        path_file = OUT / f"{stem}.postman_collection.json"
        path_file.write_text(json.dumps(coll, indent=2), encoding="utf-8")
        index.append(
            {
                "file": path_file.name,
                "name": name,
                "method": method.upper(),
                "path": path,
            }
        )

    (OUT / "INDEX.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"wrote {len(index)} collections to {OUT}")


if __name__ == "__main__":
    main()
