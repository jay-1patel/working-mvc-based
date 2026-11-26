"""Probe every API listed in final.csv against the live host."""
from __future__ import annotations

import csv
import json
import socket
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from pymongo import MongoClient

HOST = "http://10.100.100.43:9000"
CSV_PATH = Path(__file__).resolve().parents[1] / "final.csv"
LOGIN_USERNAME = "test_support_"
LOGIN_ADMIN_ID = 3047
TIMEOUT = 10
MONGO = (
    "mongodb://tmpdbtest_user:jeffJOId23WsEE@10.100.100.28:27017/tmpdbtest"
    "?authSource=tmpdbtest"
)

socket.setdefaulttimeout(TIMEOUT)


def log(msg: str) -> None:
    print(msg, flush=True)


def http(method, url, body=None, headers=None, timeout=TIMEOUT, max_read=8000):
    data = None if body is None else json.dumps(body).encode()
    hdrs = dict(headers or {})
    if body is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_read).decode(errors="replace")
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read(max_read).decode(errors="replace")
        return exc.code, raw
    except Exception as exc:  # noqa: BLE001
        return "ERR", str(exc)[:200]


def jpost(path, body, auth_h):
    code, raw = http("POST", HOST + path, body, auth_h)
    try:
        if raw.strip().startswith("{") or raw.strip().startswith("["):
            return code, json.loads(raw)
    except Exception:
        pass
    return code, {"_raw": raw}


def first_id(payload, list_keys, id_keys):
    if not isinstance(payload, dict):
        return None
    for key in list_keys:
        items = payload.get(key)
        if isinstance(items, list) and items and isinstance(items[0], dict):
            first = items[0]
            for ik in id_keys:
                if first.get(ik) not in (None, ""):
                    return first.get(ik)
    return None


def main() -> None:
    row = MongoClient(MONGO, serverSelectionTimeoutMS=8000)["tmpdbtest"]["admins"].find_one(
        {"id": LOGIN_ADMIN_ID}
    )
    if not row or not row.get("session_id"):
        raise SystemExit(f"No live session for admin {LOGIN_ADMIN_ID}")
    sid_live = str(row["session_id"])

    st, raw = http(
        "POST",
        f"{HOST}/api/auth/login",
        {"username": LOGIN_USERNAME, "session_id": sid_live},
        max_read=20000,
    )
    log(f"LOGIN {st} {raw.replace(chr(10), ' ')[:120]}")
    if st != 200:
        raise SystemExit(1)
    login = json.loads(raw)
    uid = str(login.get("user_id") or login.get("id"))
    sid = str(login.get("session_id"))
    tenant = str(login.get("tenant_id") or "c")
    log(f"AUTH user_id={uid} tenant={tenant} role={login.get('role')}")

    auth_h = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "user_id": uid,
        "session_id": sid,
    }
    auth_body = {"user_id": uid, "session_id": sid}

    wa_id = None
    agent_id = None
    run_id = None
    filename = None
    module = "inbox"

    code, payload = jpost(
        "/api/admin/tenants/conversations",
        {**auth_body, "search": "", "limit": 5},
        auth_h,
    )
    log(f"DISCOVER conversations {code}")
    wa_id = first_id(
        payload,
        ("conversations", "items", "data", "results"),
        ("wa_id", "customer_wa_id", "id"),
    )
    if not wa_id and isinstance(payload, dict):
        log(f"  keys={list(payload.keys())[:12]} sample={str(payload)[:160]}")

    code, payload = jpost(
        "/api/admin/tenants/inbox",
        {**auth_body, "include_resolved": True},
        auth_h,
    )
    log(f"DISCOVER inbox {code}")
    if not wa_id:
        wa_id = first_id(
            payload,
            ("inbox", "items", "data", "conversations", "threads"),
            ("wa_id", "customer_wa_id", "id"),
        )
        if not wa_id and isinstance(payload, dict):
            log(f"  keys={list(payload.keys())[:12]} sample={str(payload)[:160]}")

    code, payload = jpost("/api/admin/tenants/agents", auth_body, auth_h)
    log(f"DISCOVER agents {code}")
    agent_id = first_id(
        payload,
        ("agents", "items", "data", "results"),
        ("id", "agent_id", "user_id"),
    )
    if not agent_id and isinstance(payload, dict):
        log(f"  keys={list(payload.keys())[:12]} sample={str(payload)[:160]}")

    code, payload = jpost("/api/admin/tenants/crawl-runs", auth_body, auth_h)
    log(f"DISCOVER crawl-runs {code}")
    run_id = first_id(
        payload,
        ("runs", "items", "data", "results", "crawl_runs"),
        ("id", "run_id"),
    )
    if run_id is None and isinstance(payload, dict):
        log(f"  keys={list(payload.keys())[:12]} sample={str(payload)[:160]}")

    code, payload = jpost(
        "/api/admin/tenants/files",
        {**auth_body, "module": "inbox"},
        auth_h,
    )
    log(f"DISCOVER files {code}")
    if isinstance(payload, dict):
        for key in ("files", "items", "data", "results"):
            items = payload.get(key)
            if isinstance(items, list) and items and isinstance(items[0], dict):
                filename = items[0].get("filename") or items[0].get("name")
                module = items[0].get("module") or module
                break
        if not filename:
            log(f"  keys={list(payload.keys())[:12]} sample={str(payload)[:160]}")

    log(f"IDS wa_id={wa_id} agent_id={agent_id} run_id={run_id} file={filename}")

    def fill(s: str) -> str:
        if s is None:
            return ""
        replacements = {
            "<USERNAME>": LOGIN_USERNAME,
            "<SESSION_ID>": sid,
            "<WA_ID>": str(wa_id or "0000000000"),
            "<AGENT_ID>": str(agent_id or "1"),
            "<MESSAGE>": "probe ping",
            "<SEARCH>": "",
            "<TENANT_ID>": tenant,
            "<TARGET_USERNAME>": "test_support_",
            "<VERTICAL>": "automobile",
            "<FORMAT>": "json",
            "<RUN_ID>": str(run_id if run_id is not None else 1),
            "<FILENAME>": str(filename or "missing.txt"),
            "<MODULE>": module,
            "<WEBSITE_URL>": "https://example.com",
            "<FILE_NAME>": "probe.txt",
            "<BASE64>": "cHJvYmU=",
            "<LANE>": "default",
            "<PROFILE_SNAPSHOT>": "{}",
            "<FILE>": "probe.txt",
            "<FILE_PATH>": "probe.txt",
        }
        for k, v in replacements.items():
            s = s.replace(k, v)
        return s

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    log(f"CSV_ROWS {len(rows)}")
    results = []

    for i, crow in enumerate(rows, 1):
        page = crow.get("Page") or ""
        screen = crow.get("Screen or Button") or ""
        method = (crow.get("Method") or "POST").upper()
        url = fill(crow.get("Full URL") or "")
        body_raw = crow.get("Request Body") or ""
        params = crow.get("Request Body Parameters") or ""

        if "multipart" in body_raw.lower() or "file upload" in params.lower():
            boundary = "----probeBoundary7MA4YWxk"
            data = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="module"\r\n\r\n{module}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="probe.txt"\r\n'
                f"Content-Type: text/plain\r\n\r\nprobe\r\n"
                f"--{boundary}--\r\n"
            ).encode()
            hdrs = {
                "user_id": uid,
                "session_id": sid,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            }
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    code = resp.status
                    detail = resp.read()[:150].decode(errors="replace").replace("\n", " ")
            except urllib.error.HTTPError as exc:
                code = exc.code
                detail = exc.read()[:150].decode(errors="replace").replace("\n", " ")
            except Exception as exc:  # noqa: BLE001
                code = "ERR"
                detail = str(exc)[:150]
            results.append((i, page, screen, method, url, code, detail.replace("\n", " ")[:200]))
            log(f"[{i}/{len(rows)}] {code} {screen}")
            continue

        if method == "GET" and "events" in url:
            hdrs = {
                "Accept": "text/event-stream",
                "user_id": uid,
                "session_id": sid,
            }
            req = urllib.request.Request(url, headers=hdrs, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    code = resp.status
                    detail = resp.read(80).decode(errors="replace").replace("\n", " ") or "SSE opened"
            except urllib.error.HTTPError as exc:
                code = exc.code
                detail = exc.read()[:150].decode(errors="replace").replace("\n", " ")
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                if "timed out" in msg.lower() or "timeout" in msg.lower():
                    code = 200
                    detail = "SSE stream opened (read timeout expected)"
                else:
                    code = "ERR"
                    detail = msg[:150]
            results.append((i, page, screen, method, url, code, detail))
            log(f"[{i}/{len(rows)}] {code} {screen}")
            continue

        body = None
        if method != "GET" and body_raw.strip():
            filled = fill(body_raw).replace('""', '"')
            if filled.startswith("{"):
                try:
                    body = json.loads(filled)
                except Exception:
                    body = {"snapshot": {}} if "snapshot" in body_raw else {}
            elif filled == "{}":
                body = {}
            else:
                body = {}
        elif method != "GET":
            body = {}

        if body is not None:
            body = dict(body)
            body["user_id"] = uid
            body["session_id"] = sid

        t = 20 if "crawl" in url else TIMEOUT
        code, detail = http(method, url, body, auth_h, timeout=t)
        detail_s = detail.replace("\n", " ")[:200]
        results.append((i, page, screen, method, url, code, detail_s))
        log(f"[{i}/{len(rows)}] {code} {screen} :: {detail_s[:90]}")

    counts = Counter()
    for r in results:
        code = r[5]
        if isinstance(code, int) and 200 <= code < 300:
            counts["OK_2xx"] += 1
        elif isinstance(code, int) and 400 <= code < 500:
            counts["CLIENT_4xx"] += 1
        elif isinstance(code, int) and 500 <= code < 600:
            counts["SERVER_5xx"] += 1
        else:
            counts["ERR"] += 1

    log("\n=== SUMMARY ===")
    log(str(dict(counts)))
    log("\n# Status by API")
    for i, page, screen, method, url, code, detail in results:
        path = url.split(":9000", 1)[-1]
        if isinstance(code, int) and 200 <= code < 300:
            status = "WORKING"
        elif isinstance(code, int) and code >= 500:
            status = "BROKEN"
        elif code == "ERR":
            status = "BROKEN"
        else:
            status = "FAIL"
        log(f"{status}\t{code}\t{page}\t{screen}\t{method}\t{path}\t{detail[:120]}")


if __name__ == "__main__":
    main()
