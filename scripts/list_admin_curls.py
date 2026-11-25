"""Print ALL admin-panel API curls for host 10.100.100.43:9000."""
from __future__ import annotations

import base64
import csv
import re
from pathlib import Path

from pymongo import MongoClient

HOST = "http://10.100.100.43:9000"
OUT = Path(__file__).resolve().parents[1] / "scripts" / "admin_superadmin_curls_10.100.100.43.txt"
CSV_PATH = Path(__file__).resolve().parents[1] / "admin-panel-apis-integration.csv"
MONGO = (
    "mongodb://tmpdbtest_user:jeffJOId23WsEE@10.100.100.28:27017/tmpdbtest"
    "?authSource=tmpdbtest"
)


def decode_username(raw: str | None) -> str:
    value = str(raw or "")
    try:
        return base64.b64decode(value).decode()
    except Exception:
        return value


def fix_body(body: str) -> str:
    # CSV escaping sometimes breaks empty notes to: "note":"}
    body = body.replace('"note":"}', '"note":""}')
    body = body.replace("\"note\":\"}", '"note":""}')
    return body


def main() -> None:
    db = MongoClient(MONGO, serverSelectionTimeoutMS=8000)["tmpdbtest"]
    sa = None
    admin = None
    admins = []
    for row in db["admins"].find({}):
        role = str(row.get("role") or "")
        if not row.get("session_id"):
            continue
        if role == "super_admin" and sa is None:
            sa = row
        if role == "admin":
            admins.append(row)
    # Prefer tenant c (Automobile / SEND2 binding used in tests).
    for row in admins:
        if str(row.get("tenant_id") or "") == "c":
            admin = row
            break
    if admin is None and admins:
        admin = admins[0]

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)
        print(s)

    emit(f"# Host: {HOST}")
    emit("# Login uses username + session_id. All other APIs use user_id + session_id.")
    emit()
    if sa:
        emit("# --- SUPER ADMIN ---")
        emit(
            f"# username={decode_username(sa.get('username'))}  "
            f"user_id={sa.get('id')}  session_id={sa.get('session_id')}  tenant={sa.get('tenant_id')}"
        )
        emit(
            "curl -s -X POST -H 'Content-Type: application/json' "
            f"-d '{{\"username\":\"{decode_username(sa.get('username'))}\",\"session_id\":\"{sa.get('session_id')}\"}}' "
            f"'{HOST}/api/auth/login'"
        )
        emit()
    if admin:
        emit("# --- TENANT ADMIN ---")
        emit(
            f"# username={decode_username(admin.get('username'))}  "
            f"user_id={admin.get('id')}  session_id={admin.get('session_id')}  tenant={admin.get('tenant_id')}"
        )
        emit(
            "curl -s -X POST -H 'Content-Type: application/json' "
            f"-d '{{\"username\":\"{decode_username(admin.get('username'))}\",\"session_id\":\"{admin.get('session_id')}\"}}' "
            f"'{HOST}/api/auth/login'"
        )
        emit()

    emit("# After login set:")
    emit("#   USER_ID=...  SESSION_ID=...  TENANT_ID=c   (or spiritual)")
    emit()

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    emit(f"# Total APIs: {len(rows)}")
    emit()

    for i, row in enumerate(rows, 1):
        method = (row.get("http_method") or "POST").upper()
        path = (row.get("api_path") or "").split("?")[0]
        roles = row.get("roles") or ""
        section = row.get("section") or ""
        notes = row.get("notes") or ""
        curl = (row.get("curl_example") or "").replace('""', '"')
        if not path.startswith("/"):
            continue

        url_path = path
        match = re.search(r"9000(/api/[^\s\"']+)", curl)
        if match:
            url_path = match.group(1)
        url_path = (
            url_path.replace("{tenant_id}", "TENANT_ID")
            .replace("{username}", "USERNAME")
            .replace("{id}", "ID")
        )
        url_path = re.sub(r"\{[^}]+\}", "ID", url_path)

        body = '{"user_id": "USER_ID", "session_id": "SESSION_ID"}'
        body_match = re.search(r"-d '(\{.*?\})'", curl)
        if not body_match:
            body_match = re.search(r'-d "(\{.*?\})"', curl)
        if body_match:
            body = fix_body(body_match.group(1))

        emit(f"### {i}. [{section}] {method} {path}")
        emit(f"# roles: {roles}")
        if notes:
            emit(f"# notes: {notes}")

        if path == "/api/auth/login":
            emit(
                "curl -s -X POST -H 'Content-Type: application/json' "
                "-d '{\"username\":\"USERNAME\",\"session_id\":\"SESSION_ID\"}' "
                f"'{HOST}/api/auth/login'"
            )
        else:
            emit(
                f"curl -s -X {method} "
                "-H 'Content-Type: application/json' "
                "-H 'user_id: USER_ID' -H 'session_id: SESSION_ID' "
                "-H 'Accept: application/json' "
                f"-d '{body}' "
                f"'{HOST}{url_path}'"
            )
        emit()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"# Wrote {OUT}")


if __name__ == "__main__":
    main()
