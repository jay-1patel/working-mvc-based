"""Retry the failed final.csv probes with corrected placeholders."""
from __future__ import annotations

import base64
import json
import socket
import uuid
import urllib.error
import urllib.request

from pymongo import MongoClient

HOST = "http://10.100.100.43:9000"
MONGO = (
    "mongodb://tmpdbtest_user:jeffJOId23WsEE@10.100.100.28:27017/tmpdbtest"
    "?authSource=tmpdbtest"
)
socket.setdefaulttimeout(25)


def call(method, path, body=None, headers=None, timeout=15, max_read=20000):
    data = None if body is None else json.dumps(body).encode()
    hdrs = dict(headers or {})
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(HOST + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_read).decode(errors="replace")
            print(f"{resp.status} {method} {path} :: {raw.replace(chr(10), ' ')[:160]}")
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read(max_read).decode(errors="replace")
        print(f"{exc.code} {method} {path} :: {raw.replace(chr(10), ' ')[:160]}")
        return exc.code, raw
    except Exception as exc:  # noqa: BLE001
        print(f"ERR {method} {path} :: {exc}")
        return "ERR", str(exc)


def main() -> None:
    db = MongoClient(MONGO, serverSelectionTimeoutMS=8000)["tmpdbtest"]
    row = db["admins"].find_one({"id": 3047})
    sid = str(row["session_id"])
    st, raw = call(
        "POST",
        "/api/auth/login",
        {"username": "test_support_", "session_id": sid},
    )
    login = json.loads(raw)
    uid = str(login["user_id"])
    sid = str(login["session_id"])
    auth = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "user_id": uid,
        "session_id": sid,
    }
    body_base = {"user_id": uid, "session_id": sid}

    print("--- crawl with real run_id ---")
    call("POST", "/api/admin/tenants/crawl-runs/staged", {**body_base, "run_id": 82}, auth)
    call(
        "POST",
        "/api/admin/tenants/crawl-runs/export",
        {**body_base, "run_id": 82, "format": "json"},
        auth,
    )
    call("POST", "/api/admin/tenants/crawl-runs/staged", {**body_base, "run_id": 83}, auth)

    print("--- kit formats ---")
    call("GET", "/api/admin/onboarding-kits/automobile/docx", None, auth)
    call("GET", "/api/admin/onboarding-kits/real_estate/docx", None, auth)
    call("GET", "/api/admin/onboarding-kits/automotive/docx", None, auth)

    print("--- multipart upload ---")
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]
    payload = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="module"\r\n\r\ninbox\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="probe.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\nhello probe\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        HOST + "/api/admin/tenants/files/upload",
        data=payload,
        headers={
            "user_id": uid,
            "session_id": sid,
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(
                "UPLOAD",
                resp.status,
                resp.read(200).decode(errors="replace").replace("\n", " ")[:160],
            )
    except urllib.error.HTTPError as exc:
        print(
            "UPLOAD",
            exc.code,
            exc.read(250).decode(errors="replace").replace("\n", " ")[:200],
        )
    except Exception as exc:  # noqa: BLE001
        print("UPLOAD ERR", exc)

    st, files_raw = call(
        "POST",
        "/api/admin/tenants/files",
        {**body_base, "module": "inbox"},
        auth,
    )
    filename = None
    try:
        files = json.loads(files_raw).get("files") or []
        if files:
            filename = files[0].get("filename") or files[0].get("name")
    except Exception:
        pass
    print("filename=", filename)
    if filename:
        call(
            "POST",
            "/api/admin/tenants/files/preview",
            {**body_base, "filename": filename, "module": "inbox"},
            auth,
        )
        call(
            "POST",
            "/api/admin/tenants/files/download",
            {**body_base, "filename": filename, "module": "inbox"},
            auth,
        )
        call(
            "POST",
            "/api/admin/tenants/files/delete",
            {**body_base, "filename": filename, "module": "inbox"},
            auth,
        )

    print("--- onboarding stage short payload ---")
    call(
        "POST",
        "/api/admin/onboarding/stage",
        {
            **body_base,
            "files": [{"filename": "probe.txt", "content": "cHJvYmU="}],
        },
        auth,
        timeout=30,
    )

    print("--- super admin onboard users ---")
    sa = None
    for a in db["admins"].find({"role": "super_admin"}):
        if a.get("session_id"):
            sa = a
            break
    print("SA found", bool(sa), "id", (sa or {}).get("id"))
    if not sa:
        return
    uname = sa.get("username")
    try:
        uname = base64.b64decode(uname).decode()
    except Exception:
        uname = str(uname)
    st, raw = call(
        "POST",
        "/api/auth/login",
        {"username": uname, "session_id": str(sa["session_id"])},
    )
    if st != 200:
        print("SA login fail")
        return
    sa_login = json.loads(raw)
    suid = str(sa_login["user_id"])
    ssid = str(sa_login["session_id"])
    sa_auth = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "user_id": suid,
        "session_id": ssid,
    }
    call("POST", "/api/auth/onboarding-users", {"user_id": suid, "session_id": ssid}, sa_auth)


if __name__ == "__main__":
    main()
