"""Acceptance checks for the Send2 credential vault (throwaway tenant only).

Never prints credential values. Exit non-zero on failure.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ADMIN_SECRET_KEY", "acceptance-vault-key")
os.environ["ROUTING_DB_PATH"] = str(ROOT / "legacy-unused-acceptance.db")

# Ephemeral master key for this throwaway run — never printed.
_MASTER = base64.b64encode(os.urandom(32)).decode("ascii")
os.environ["CREDENTIAL_MASTER_KEY"] = _MASTER

from mongo_test_support import MongomockSession
import database
from services import credential_master_key as master_key_mod
from services import credential_vault as vault

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def main():
    mongo = MongomockSession().start()
    database.init_db()

    test_user = "accept-vault-user"
    test_pass = "AcceptVault-Pass-NEVER-LOG-zz9"
    tenant = "vault-accept-throwaway"
    krt = "krt-accept-throwaway"

    # 2. Store then search raw collection for plaintext
    vault.store_send2_credentials(tenant, krt, test_user, test_pass, {"note": "accept"})
    raw = mongo.database["send2_credentials"].find_one({"tenant_id": tenant})
    blob = str(raw)
    check(
        "AT2 plaintext absent from raw collection",
        test_user not in blob and test_pass not in blob,
        f"keys={sorted(k for k in raw.keys() if not k.startswith('_'))}",
    )

    # 3. Session scoping is covered by unit tests; mirror here with vault get
    vault.store_send2_credentials("tenant-other", "krt-other", "other-u", "other-p", {})
    a = vault.get_send2_credentials(tenant)
    b = vault.get_send2_credentials("tenant-other")
    check(
        "AT3 tenant isolation of vault records",
        a["username"] == test_user and b["username"] == "other-u" and a["password"] != b["password"],
    )

    # 4a. Resolve vault credentials (session-token path input)
    u, p = vault.resolve_send2_username_password(tenant)
    check("AT4a vault resolve for throwaway tenant", u == test_user and p == test_pass)

    # 4b. Real Send2 session-msg-send probe using vault-resolved env pair when present
    from routing.config import SEND2_SESSION_SEND_URL, SEND2_USERNAME, SEND2_PASSWORD
    real_ok = False
    real_detail = "skipped — no SEND2_USERNAME/PASSWORD or SEND2_SESSION_SEND_URL in env"
    if SEND2_USERNAME and SEND2_PASSWORD and SEND2_SESSION_SEND_URL:
        # Store the live pair under a second throwaway tenant, never log values.
        live_tenant = "vault-accept-live-probe"
        vault.store_send2_credentials(
            live_tenant, "krt-live-probe", SEND2_USERNAME, SEND2_PASSWORD, {}
        )
        vu, vp = vault.resolve_send2_username_password(live_tenant)
        import httpx
        # Probe contact is a placeholder; Send2 may reject it — we only check auth.
        payload = {
            "user_name": vu,
            "password": vp,
            "contact_no": "0000000000",
            "message_type": "text",
            "message": "vault-accept-probe",
        }
        try:
            resp = httpx.post(SEND2_SESSION_SEND_URL, json=payload, timeout=20)
            # Auth success is any non-401/403; Send2 may reject the contact.
            real_ok = resp.status_code not in (401, 403)
            real_detail = f"HTTP {resp.status_code} (auth accepted={real_ok})"
        except Exception as exc:
            real_ok = False
            real_detail = f"request error: {type(exc).__name__}"
    check("AT4b real Send2 session call via vault credentials", real_ok, real_detail)

    # 4c. Fallback path warning
    with patch.dict(
        os.environ,
        {
            "SEND2_VAULT_FALLBACK": "true",
            "SEND2_USERNAME": "fallback-user",
            "SEND2_PASSWORD": "fallback-pass",
        },
        clear=False,
    ):
        with patch("routing.config.SEND2_USERNAME", "fallback-user"), patch(
            "routing.config.SEND2_PASSWORD", "fallback-pass"
        ):
            log_buf = io.StringIO()
            handler = logging.StreamHandler(log_buf)
            logging.getLogger("credential_vault").addHandler(handler)
            fu, fp = vault.resolve_send2_username_password("no-such-tenant-xyz")
            logging.getLogger("credential_vault").removeHandler(handler)
            logs = log_buf.getvalue()
            check(
                "AT4c fallback warning + env pair",
                fu == "fallback-user"
                and fp == "fallback-pass"
                and "SEND2_VAULT_FALLBACK_USED" in logs
                and "fallback-pass" not in logs,
                "warning present; password absent from log excerpt",
            )

    # 5. Grep acceptance logs for test password
    log_capture = io.StringIO()
    root_handler = logging.StreamHandler(log_capture)
    logging.getLogger().addHandler(root_handler)
    logging.getLogger("credential_vault").addHandler(root_handler)
    vault.get_send2_credentials(tenant)
    sync_logs = log_capture.getvalue()
    logging.getLogger().removeHandler(root_handler)
    logging.getLogger("credential_vault").removeHandler(root_handler)
    check(
        "AT5 test password absent from vault logs",
        test_pass not in sync_logs,
        f"log_chars={len(sync_logs)} matches={sync_logs.count(test_pass)}",
    )

    # 6. Startup fails without CREDENTIAL_MASTER_KEY
    with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
        os.environ.pop("CREDENTIAL_MASTER_KEY", None)
        err = io.StringIO()
        from contextlib import redirect_stderr
        raised = False
        with redirect_stderr(err):
            try:
                master_key_mod.require_credential_master_key_at_startup()
            except SystemExit:
                raised = True
        out = err.getvalue()
        check(
            "AT6 startup fails when CREDENTIAL_MASTER_KEY missing",
            raised
            and "CREDENTIAL_MASTER_KEY" in out
            and master_key_mod.GENERATE_HINT in out
            and _MASTER not in out,
            "clear error + generate command; no key value leaked",
        )

    mongo.stop()
    print(f"\nAcceptance summary: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
