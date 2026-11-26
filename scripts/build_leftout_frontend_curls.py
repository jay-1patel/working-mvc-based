"""Build curl-only list of frontend APIs missing from final.csv."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "final.csv"
OUT = ROOT / "leftout-frontend-apis-curls.txt"
HOST = "http://10.100.100.43:9000"
T = "TENANT_ID"

# Explicit frontend API inventory (path, method) — non-test production calls.
# Placeholders: TENANT_ID, USERNAME, ID, WA_ID, PROVIDER, AWB, INTENT, KEY, FORMAT
FRONTEND_APIS: list[tuple[str, str, str]] = [
    # Auth / session
    ("Auth", "POST", "/api/auth/status"),
    ("Auth", "POST", "/api/auth/login"),
    ("Auth", "POST", "/api/auth/me"),
    ("Auth", "POST", "/api/auth/first-admin"),
    ("Auth", "POST", "/api/auth/first-login/complete"),
    ("Auth", "POST", "/api/auth/admins"),
    ("Auth", "POST", "/api/auth/create"),
    ("Auth", "POST", "/api/auth/admins/<USERNAME>/update"),
    ("Auth", "POST", "/api/auth/admins/<USERNAME>/delete"),
    ("Auth", "POST", "/api/auth/admins/<USERNAME>/reset-password"),
    ("Auth", "POST", "/api/auth/impersonate-tenant/<TENANT_ID>"),
    # Dashboard / errors
    ("Dashboard", "POST", "/api/admin/dashboard/overview?days=7&limit=8"),
    ("Dashboard", "GET", "/api/admin/errors?limit=100"),
    # Tenants admin
    ("Tenants", "POST", "/api/admin/tenants/list"),
    ("Tenants", "POST", "/api/admin/tenants"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/delete"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/detail"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/phone-id"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/intents/<INTENT>"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/versions"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/versions/<VERSION>"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/rollback"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/tokens/list"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/tokens"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/tokens/<TOKEN_ID>/delete"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/test-question"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/smoke"),
    ("Tenants", "POST", "/api/admin/tenants/active-test-tenant/current"),
    ("Tenants", "POST", "/api/admin/tenants/active-test-tenant"),
    ("Tenants", "POST", "/api/admin/tenants/send2-credentials/status"),
    ("Tenants", "POST", "/api/admin/tenants/<TENANT_ID>/send2-credentials/resync"),
    # Approvals
    ("Approvals", "POST", "/api/tenant-change-requests/mine"),
    ("Approvals", "POST", "/api/tenant-change-requests"),
    ("Approvals", "POST", "/api/admin/tenant-change-requests"),
    ("Approvals", "POST", "/api/admin/tenant-change-requests/<ID>/decision"),
    ("Approvals", "POST", "/api/admin/tenant-change-requests/<ID>/events"),
    # Audit
    ("Audit", "POST", "/api/admin/audit-history"),
    ("Audit", "POST", "/api/admin/audit-history/<EVENT_ID>"),
    ("Audit", "POST", "/api/admin/audit-statistics"),
    ("Audit", "POST", "/api/admin/audit-export"),
    # Chats extras
    ("Chats", "POST", "/api/admin/tenants/chat-history"),
    ("Chats", "POST", "/api/admin/tenants/inbox/attach"),
    ("Chats", "POST", "/api/admin/tenants/<TENANT_ID>/chat/attach"),
    ("Chats", "POST", "/api/admin/tenants/<TENANT_ID>/chat/users"),
    ("Chats", "POST", "/api/admin/tenants/<TENANT_ID>/chat/send"),
    ("Chats", "POST", "/api/admin/tenants/complaints"),
    ("Chats", "POST", "/api/admin/tenants/complaints/update"),
    ("Chats", "POST", "/api/admin/tenants/complaints/reply"),
    ("Chats", "POST", "/api/admin/tenants/complaints/delete"),
    # Files / KB extras
    ("Files", "POST", "/api/admin/tenants/files/bifurcate-existing"),
    ("Files", "POST", "/api/admin/tenants/<TENANT_ID>/files/auto-bifurcate"),
    ("Files", "POST", "/api/admin/tenants/<TENANT_ID>/files/image"),
    ("Files", "POST", "/api/admin/tenants/knowledge-gaps"),
    ("Files", "POST", "/api/admin/tenants/knowledge-gaps/resolve"),
    ("Files", "POST", "/api/admin/tenants/knowledge-gaps/create-faq"),
    ("Files", "POST", "/api/admin/upload/logo"),
    # Offerings / schema
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/offerings/list"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/offerings"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/offerings/<ID>/update"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/offerings/<ID>/delete"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/record-schema"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/record-schema/columns"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/record-schema/columns/<KEY>/update"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/record-schema/columns/<KEY>/delete"),
    ("Offerings", "POST", "/api/admin/tenants/<TENANT_ID>/record-schema/reset"),
    # Orders / customers (legacy + tenant)
    ("Operations", "GET", "/api/admin/customers"),
    ("Operations", "GET", "/api/orders"),
    ("Operations", "POST", "/api/admin/tenants/<TENANT_ID>/orders"),
    # Campaigns
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/list"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/<ID>/update"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/<ID>/delete"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/<ID>/send"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/<ID>/send-selection"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/<ID>/test-send"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/recipients"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/media"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/templates/list"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/templates"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/templates/<ID>/update"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/templates/<ID>/delete"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/segments/list"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/segments"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/segments/<ID>/update"),
    ("Campaigns", "POST", "/api/admin/tenants/<TENANT_ID>/campaigns/segments/<ID>/delete"),
    # Distributors
    ("Distributors", "POST", "/api/admin/tenants/<TENANT_ID>/distributors/list"),
    ("Distributors", "POST", "/api/admin/tenants/<TENANT_ID>/distributors"),
    ("Distributors", "POST", "/api/admin/tenants/<TENANT_ID>/distributors/<WA_ID>/update"),
    ("Distributors", "POST", "/api/admin/tenants/<TENANT_ID>/distributors/<WA_ID>/delete"),
    # Callbacks
    ("Callbacks", "POST", "/api/tenants/<TENANT_ID>/callbacks/list"),
    ("Callbacks", "POST", "/api/tenants/<TENANT_ID>/callbacks"),
    ("Callbacks", "POST", "/api/tenants/<TENANT_ID>/callbacks/<ID>/cancel"),
    ("Callbacks", "POST", "/api/tenants/<TENANT_ID>/callbacks/<ID>/complete"),
    ("Callbacks", "POST", "/api/tenants/<TENANT_ID>/callbacks/<ID>/schedule"),
    # Integrations / payments / shipping
    ("Integrations", "POST", "/api/integration-requests/mine"),
    ("Integrations", "POST", "/api/integration-requests"),
    ("Integrations", "POST", "/api/admin/integration-requests"),
    ("Integrations", "POST", "/api/admin/integration-requests/<ID>/decision"),
    ("Integrations", "POST", "/api/admin/integration-requests/<ID>/events"),
    ("Integrations", "POST", "/api/tenants/<TENANT_ID>/integrations"),
    ("Integrations", "POST", "/api/tenants/<TENANT_ID>/integrations/<PROVIDER>/config"),
    ("Integrations", "POST", "/api/tenants/<TENANT_ID>/integrations/<PROVIDER>/test"),
    ("Integrations", "POST", "/api/tenants/<TENANT_ID>/payments/create-session"),
    ("Integrations", "POST", "/api/tenants/<TENANT_ID>/shipping/book-shipment"),
    ("Integrations", "POST", "/api/tenants/<TENANT_ID>/shipping/track/<AWB>"),
    # Simulator
    ("Simulator", "POST", "/api/test-simulator"),
    ("Simulator", "POST", "/api/test-simulator/reset"),
]


def csv_path_set() -> set[str]:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    out: set[str] = set()
    for row in rows:
        url = (row.get("Full URL") or "").strip()
        m = re.search(r"https?://[^/]+(/api/.+)$", url)
        if not m:
            continue
        p = m.group(1).split("?")[0]
        p = p.replace("<TARGET_USERNAME>", "<USERNAME>")
        out.add(p)
    return out


def canon(path: str) -> str:
    p = path.split("?")[0]
    p = re.sub(r"<[^>]+>", "*", p)
    return p


def curl_line(method: str, path: str) -> str:
    url_path = (
        path.replace("<TENANT_ID>", T)
        .replace("<USERNAME>", "USERNAME")
        .replace("<INTENT>", "INTENT")
        .replace("<VERSION>", "1")
        .replace("<TOKEN_ID>", "1")
        .replace("<EVENT_ID>", "1")
        .replace("<ID>", "1")
        .replace("<KEY>", "KEY")
        .replace("<WA_ID>", "919999999999")
        .replace("<PROVIDER>", "PROVIDER")
        .replace("<AWB>", "AWB")
        .replace("<FORMAT>", "docx")
    )
    url = HOST + url_path
    auth = '-H "user_id: USER_ID" -H "session_id: SESSION_ID"'
    if method == "GET":
        return f'curl -s -X GET {auth} "{url}"'
    if path.endswith("/media") or path.endswith("/attach") or path.endswith("/image") or path.endswith("/upload/logo"):
        return f'curl -s -X POST {auth} -F "file=@FILE_PATH" "{url}"'
    return (
        f'curl -s -X {method} -H "Content-Type: application/json" {auth} '
        f'-d \'{{"user_id":"USER_ID","session_id":"SESSION_ID"}}\' "{url}"'
    )


def main() -> None:
    csv_paths = csv_path_set()
    csv_canon = {canon(p) for p in csv_paths}

    missing = []
    for area, method, path in FRONTEND_APIS:
        if canon(path) in csv_canon:
            continue
        missing.append((area, method, path))

    lines = [
        "# Frontend APIs NOT listed in final.csv — curl only",
        f"# Host: {HOST}",
        "# Replace USER_ID / SESSION_ID / TENANT_ID / placeholders before use",
        f"# Count: {len(missing)}",
        "",
    ]
    current_area = None
    for i, (area, method, path) in enumerate(missing, 1):
        if area != current_area:
            lines.append(f"# ===== {area} =====")
            current_area = area
        lines.append(f"# {i}. {method} {path}")
        lines.append(curl_line(method, path))
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"final.csv unique paths: {len(csv_paths)}")
    print(f"frontend inventory: {len(FRONTEND_APIS)}")
    print(f"left out (not in final.csv): {len(missing)}")
    print(f"wrote: {OUT}")
    for area, method, path in missing:
        print(f"{area}\t{method}\t{path}")


if __name__ == "__main__":
    main()
