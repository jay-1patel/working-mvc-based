"""Probe admin-panel APIs against a live host and print status summary."""
from __future__ import annotations

import csv
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

HOST = "http://10.100.100.43:9000"
CSV_PATH = Path(__file__).resolve().parents[1] / "admin-panel-apis-integration.csv"
LOGIN_USERNAME = "test_support_"
LOGIN_ADMIN_ID = 3047
TIMEOUT_SEC = 8


def log(msg: str) -> None:
    print(msg, flush=True)


def live_session_id() -> str:
    from pymongo import MongoClient

    uri = (
        "mongodb://tmpdbtest_user:jeffJOId23WsEE@10.100.100.28:27017/tmpdbtest"
        "?authSource=tmpdbtest"
    )
    row = MongoClient(uri, serverSelectionTimeoutMS=8000)["tmpdbtest"]["admins"].find_one(
        {"id": LOGIN_ADMIN_ID}
    )
    if not row or not row.get("session_id"):
        raise RuntimeError(f"No live session_id for admin {LOGIN_ADMIN_ID}")
    return str(row["session_id"])


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers or {"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"_raw": raw[:200]}
            return resp.status, parsed, ""
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        return exc.code, {}, raw[:160].replace("\n", " ")
    except Exception as exc:  # noqa: BLE001 - probe tool
        return "ERR", {}, str(exc)[:160]


def pick(row: dict, *keys: str) -> str:
    for key in keys:
        if key in row and row[key]:
            return str(row[key]).strip()
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        val = lower.get(key.lower())
        if val:
            return str(val).strip()
    return ""


def fill_path(path: str) -> str:
    path = path.split("?")[0]
    path = (
        path.replace("{tenant_id}", "c")
        .replace("{username}", "test_support_")
        .replace("{id}", "1")
    )
    return re.sub(r"\{[^}]+\}", "1", path)


SKIP_SUBSTRINGS = (
    "/delete",
    "/decision",
    "/publish",
    "/regenerate-session",
    "/first-login/complete",
    "/create",
    "/update",
    "/impersonate",
    "/active-test-tenant",
    "/resync",
    "/bind",
    "/unbind",
    "/approve",
    "/reject",
    "/upload",
    "/import",
    "/export",
    "/send",
    "/start",
    "/stop",
    "/reset",
    "/wipe",
    "/seed",
    "/events",  # SSE / long-poll hangs probes
    "/stream",
)


def main() -> None:
    import socket

    socket.setdefaulttimeout(TIMEOUT_SEC)
    login_session = live_session_id()
    log(f"USING_SESSION {login_session}")
    status, login, err = http_json(
        "POST",
        f"{HOST}/api/auth/login",
        {"username": LOGIN_USERNAME, "session_id": login_session},
    )
    if status != 200:
        log(f"LOGIN_FAIL {status} {err or login}")
        raise SystemExit(1)

    uid = str(login.get("user_id") or login.get("id") or "")
    sid = str(login.get("session_id") or "")
    log(
        f"LOGIN_OK {status} user_id={uid} role={login.get('role')} "
        f"tenant_id={login.get('tenant_id')} session={sid[:36]}..."
    )

    auth_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "user_id": uid,
        "session_id": sid,
    }
    auth_body = {"user_id": uid, "session_id": sid}

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    log(f"CSV_ROWS {len(rows)}")

    seen: set[tuple[str, str]] = set()
    endpoints: list[tuple[str, str, str]] = []
    for row in rows:
        method = (pick(row, "http_method", "method") or "POST").upper()
        path = pick(row, "api_path", "path")
        if not path:
            curl = pick(row, "curl_example", "curl")
            match = re.search(r"https?://[^\s\"']+(/api/[^\s\"']+)", curl or "")
            if match:
                path = match.group(1)
        if not path.startswith("/"):
            continue
        path = path.split("?")[0]
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        endpoints.append((method, path, pick(row, "section")))

    log(f"UNIQUE_ENDPOINTS {len(endpoints)}")

    results: list[tuple[object, str, str, str, str]] = []
    for idx, (method, path, area) in enumerate(endpoints, 1):
        if path == "/api/auth/login":
            results.append((200, "LOGIN_OK", method, path, area))
            log(f"[{idx}/{len(endpoints)}] 200 LOGIN_OK {path}")
            continue
        if any(s in path for s in SKIP_SUBSTRINGS):
            results.append(("SKIP", "mutating skipped", method, path, area))
            log(f"[{idx}/{len(endpoints)}] SKIP {path}")
            continue

        url = HOST + fill_path(path)
        code, _payload, detail = http_json(
            method if method != "GET" else "GET",
            url,
            None if method == "GET" else auth_body,
            auth_headers,
        )
        results.append((code, detail or "OK", method, path, area))
        log(f"[{idx}/{len(endpoints)}] {code} {method} {path} {detail[:80]}")

    summary = Counter(r[0] for r in results)
    log(f"SUMMARY {dict(summary)}")

    ok = [r for r in results if isinstance(r[0], int) and 200 <= r[0] < 300]
    bad = [r for r in results if not (isinstance(r[0], int) and 200 <= r[0] < 300) and r[0] != "SKIP"]
    skipped = [r for r in results if r[0] == "SKIP"]

    log("--- NON_2XX ---")
    for code, detail, method, path, area in bad:
        log(f"{code}\t{method}\t{path}\t{area}\t{detail}")

    log(f"OK_COUNT={len(ok)} SKIP={len(skipped)} FAIL={len(bad)} TOTAL={len(results)}")


if __name__ == "__main__":
    main()
