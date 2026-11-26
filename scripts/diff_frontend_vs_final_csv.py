"""Diff frontend /api calls against final.csv and emit curl-only for missing ones."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "final.csv"
FRONTEND_SRC = ROOT / "frontend" / "src"
OUT = ROOT / "leftout-frontend-apis-curls.txt"
HOST = "http://10.100.100.43:9000"

API_RE = re.compile(
    r"""(?:['"`]|apiUrl\(['"`]|fetch\(['"`]|api\.(?:post|get|put|delete|patch|postForm)\(\s*['"`])"""
    r"""(/api/[A-Za-z0-9_\-./${}`?=&+%]+)"""
)
# Also catch template literals built as `/api/...${...}`
API_TEMPLATE_RE = re.compile(r"""[`'"](/api/[A-Za-z0-9_\-./${}]+)[`'"]""")
METHOD_HINT = re.compile(
    r"""api\.(post|get|put|delete|patch|postForm)\(\s*[`'"](/api/[^`'"]+)[`'"]"""
)
FETCH_METHOD = re.compile(
    r"""fetch\(\s*(?:apiUrl\()?[`'"](/api/[^`'"]+)[`'"]\)?\s*,\s*\{[^}]*method\s*:\s*['"]([A-Z]+)['"]""",
    re.I | re.S,
)

SKIP_PREFIXES = (
    "/api/logos/",
    "/api/uploads/",
    "/api/client-errors",  # telemetry
)


def normalize_path(path: str) -> str:
    path = path.split("?")[0]
    path = path.replace("${encodeURIComponent(tenantId)}", "<TENANT_ID>")
    path = path.replace("${encodeURIComponent(id)}", "<TENANT_ID>")
    path = path.replace("${encodeURIComponent(username)}", "<USERNAME>")
    path = path.replace("${encodeURIComponent(provider)}", "<PROVIDER>")
    path = path.replace("${encodeURIComponent(awb)}", "<AWB>")
    path = path.replace("${encodeURIComponent(intent)}", "<INTENT>")
    path = path.replace("${encodeURIComponent(slug)}", "<VERTICAL>")
    path = path.replace("${encodeURIComponent(tokenId)}", "<TOKEN_ID>")
    path = path.replace("${version}", "<VERSION>")
    path = path.replace("${tokenId}", "<TOKEN_ID>")
    path = path.replace("${id}", "<ID>")
    path = path.replace("${eventId}", "<EVENT_ID>")
    path = path.replace("${format}", "<FORMAT>")
    path = path.replace("${area === 'chat' ? `${base(tenantId)}/chat/attach` : '", "")
    # generic ${...}
    path = re.sub(r"\$\{[^}]+\}", "<PARAM>", path)
    path = path.replace("//", "/")
    if path.endswith("/"):
        path = path[:-1]
    return path


def csv_paths() -> set[str]:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    found: set[str] = set()
    for row in rows:
        url = (row.get("Full URL") or "").strip()
        m = re.search(r"https?://[^/]+(/api/.+)$", url)
        if m:
            p = m.group(1)
            p = p.replace("<TENANT_ID>", "<TENANT_ID>")
            p = p.replace("<TARGET_USERNAME>", "<USERNAME>")
            p = p.replace("<VERTICAL>", "<VERTICAL>")
            p = p.replace("<FORMAT>", "<FORMAT>")
            p = re.sub(r"<[^>]+>", lambda x: x.group(0), p)
            # unify placeholders used in CSV
            p = p.replace("<TARGET_USERNAME>", "<USERNAME>")
            found.add(normalize_path(p))
            # also store without query
            found.add(normalize_path(p.split("?")[0]))
    return found


def extract_frontend() -> dict[str, set[str]]:
    """path -> set of methods hinted"""
    hits: dict[str, set[str]] = {}
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if "test" in path.parts or "fixture" in path.name.lower():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")

        for m in METHOD_HINT.finditer(text):
            method = m.group(1).upper()
            if method == "POSTFORM":
                method = "POST"
            api_path = normalize_path(m.group(2))
            hits.setdefault(api_path, set()).add(method)

        for m in FETCH_METHOD.finditer(text):
            api_path = normalize_path(m.group(1))
            hits.setdefault(api_path, set()).add(m.group(2).upper())

        for m in API_TEMPLATE_RE.finditer(text):
            api_path = normalize_path(m.group(1))
            if not api_path.startswith("/api/"):
                continue
            hits.setdefault(api_path, set())

        # special patterns in offerings/operations/attachments
        for m in re.finditer(
            r"""[`'"](/api/admin/tenants/\$\{[^}]+\}/[A-Za-z0-9_\-./${}]+)[`'"]""",
            text,
        ):
            api_path = normalize_path(m.group(1))
            hits.setdefault(api_path, set())

    return hits


def path_in_csv(path: str, csv_set: set[str]) -> bool:
    n = normalize_path(path)
    if n in csv_set:
        return True
    # soft match: replace placeholders and compare structure
    def canon(p: str) -> str:
        p = normalize_path(p)
        p = re.sub(r"<[^>]+>", "*", p)
        p = re.sub(r"/[0-9]+(?=/|$)", "/*", p)
        return p

    cn = canon(n)
    return any(canon(c) == cn for c in csv_set)


def curl_for(method: str, path: str) -> str:
    url = HOST + path.replace("<TENANT_ID>", "TENANT_ID").replace("<USERNAME>", "USERNAME")
    url = (
        url.replace("<PROVIDER>", "PROVIDER")
        .replace("<AWB>", "AWB")
        .replace("<INTENT>", "INTENT")
        .replace("<VERTICAL>", "VERTICAL")
        .replace("<FORMAT>", "docx")
        .replace("<TOKEN_ID>", "TOKEN_ID")
        .replace("<VERSION>", "1")
        .replace("<ID>", "1")
        .replace("<EVENT_ID>", "1")
        .replace("<PARAM>", "PARAM")
    )
    auth_h = '-H "user_id: USER_ID" -H "session_id: SESSION_ID"'
    if method == "GET":
        return f'curl -s -X GET {auth_h} "{url}"'
    if "upload/logo" in path or "attach" in path:
        return (
            f'curl -s -X POST {auth_h} '
            f'-F "file=@FILE_PATH" "{url}"'
        )
    body = '{"user_id":"USER_ID","session_id":"SESSION_ID"}'
    return (
        f'curl -s -X {method} -H "Content-Type: application/json" {auth_h} '
        f"-d '{body}' \"{url}\""
    )


def main() -> None:
    csv_set = csv_paths()
    front = extract_frontend()

    missing: list[tuple[str, str]] = []
    for path, methods in sorted(front.items()):
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            continue
        if path_in_csv(path, csv_set):
            continue
        method = next(iter(methods)) if methods else "POST"
        # default POST for panel APIs
        if not methods:
            method = "GET" if "?" in path or path.endswith("/events") else "POST"
        if "errors" in path and "client-errors" not in path:
            method = "GET"
        if path.endswith("/events") and "inbox" not in path:
            method = "POST"
        missing.append((method, path))

    # Deduplicate by normalized path keeping first method
    seen = set()
    uniq = []
    for method, path in missing:
        if path in seen:
            continue
        seen.add(path)
        uniq.append((method, path))

    lines = [
        "# Frontend APIs NOT in final.csv — curl only",
        f"# Host: {HOST}",
        "# Replace USER_ID / SESSION_ID / TENANT_ID / placeholders before use",
        f"# Count: {len(uniq)}",
        "",
    ]
    for i, (method, path) in enumerate(uniq, 1):
        lines.append(f"# {i}. {method} {path}")
        lines.append(curl_for(method, path))
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"CSV paths: {len(csv_set)}")
    print(f"Frontend paths: {len(front)}")
    print(f"Missing: {len(uniq)}")
    print(f"Wrote: {OUT}")
    for method, path in uniq:
        print(f"{method}\t{path}")


if __name__ == "__main__":
    main()
