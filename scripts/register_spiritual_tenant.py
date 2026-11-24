"""Register spiritual tenant + admin with Send2 base64 credentials."""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

# Load routing/.env into process env (do not override existing).
env_path = ROOT / "routing" / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)

os.environ.setdefault("DATABASE_BACKEND", "mongodb")

from core.send2_auth import encode_send2_username  # noqa: E402
from db.mongo import Repository  # noqa: E402
from routes.auth import SUPER_ADMIN_PERMISSIONS  # noqa: E402
from shared.tenancy import store as tenancy_store  # noqa: E402

PLAIN_USERNAME = "spiritual"
PLAIN_PASSWORD = "6s@g@kwi"
ENCODED_USERNAME = "c3Bpcml0dWFs"
ENCODED_PASSWORD = "NnNAZ0Brd2k="
KRT_UNIQUE_ID = "7K9TF"
COMPANY_NAME = "LEEWAY SOFT TECH PRIVATE LIMITED"
TENANT_ID = "spiritual"


def main() -> int:
    # Verify senior-provided encodings match the Send2 helper.
    computed_user = encode_send2_username(PLAIN_USERNAME)
    if computed_user != ENCODED_USERNAME:
        raise SystemExit(f"username encode mismatch: {computed_user!r} != {ENCODED_USERNAME!r}")

    import base64

    computed_pass = base64.b64encode(PLAIN_PASSWORD.encode("utf-8")).decode("ascii")
    if computed_pass != ENCODED_PASSWORD:
        raise SystemExit(f"password encode mismatch: {computed_pass!r} != {ENCODED_PASSWORD!r}")

    existing = Repository("admins").find_one({"username": ENCODED_USERNAME})
    if existing:
        print(f"admin already exists id={existing.get('id')} tenant_id={existing.get('tenant_id')}")
    else:
        session_id = secrets.token_urlsafe(32)
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row = Repository("admins").insert(
            {
                "username": ENCODED_USERNAME,
                # Store Send2-style base64 password as requested (both fields).
                "password": ENCODED_PASSWORD,
                "password_hash": ENCODED_PASSWORD,
                "salt": None,
                "role": "admin",
                "permissions": dict(SUPER_ADMIN_PERMISSIONS),
                "recovery_key": None,
                "tenant_id": TENANT_ID,
                "session_id": session_id,
                "email": None,
                "krt_unique_id": KRT_UNIQUE_ID,
                "name": COMPANY_NAME,
                "services": "AiChatbot",
                "user_type_di": "Domestic",
                "flag": 1,
                "login_status": 1,
                "created_at": now,
                "updated_at": now,
            }
        )
        print(
            "admin created",
            {
                "id": row.get("id"),
                "username": ENCODED_USERNAME,
                "password": ENCODED_PASSWORD,
                "krt_unique_id": KRT_UNIQUE_ID,
                "tenant_id": TENANT_ID,
                "role": "admin",
                "session_id": session_id,
            },
        )

    tenancy_store.ensure_tenant(
        TENANT_ID,
        slug=TENANT_ID,
        vertical="generic",
        display_name=COMPANY_NAME,
        status="active",
    )
    tenant = tenancy_store.get_tenant(TENANT_ID) or {}
    print(
        "tenant ready",
        {
            "id": tenant.get("id"),
            "slug": tenant.get("slug"),
            "display_name": tenant.get("display_name"),
            "status": tenant.get("status"),
            "vertical": tenant.get("vertical"),
        },
    )

    # Confirm lookup path used by login (plain → encode → find).
    found = Repository("admins").find_one({"username": encode_send2_username(PLAIN_USERNAME)})
    print(
        "login lookup ok",
        bool(found),
        "role=",
        (found or {}).get("role"),
        "tenant_id=",
        (found or {}).get("tenant_id"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
