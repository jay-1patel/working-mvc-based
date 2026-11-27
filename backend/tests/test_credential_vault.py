"""Phase 2 unit tests + Phase 3/4/6 acceptance checks for the Send2 vault."""

from __future__ import annotations

import base64
import io
import logging
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
for _path in (str(TESTS_DIR), str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from mongo_test_support import MongomockSession

import database
from core.send2_auth import encode_send2_username
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import auth as auth_routes
from routes import send2_credentials as send2_cred_routes
from services import credential_master_key as master_key_mod
from services import credential_vault as vault
from services.send2_credentials_sync import (
    Send2CredentialsApiNotConfigured,
    send2_fetch_credentials,
    sync_send2_credentials,
)


def _ephemeral_master_key() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


SAMPLE_SEND2_RESPONSE = {
    "customer_id": "krt-vault-demo",
    "username": "vault-demo-user",
    "password": "VaultDemo-Pass-NeverLog",
    "extra": {"region": "in"},
}


class CredentialMasterKeyTests(unittest.TestCase):
    def test_missing_key_dev_prints_generate_command(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            os.environ.pop(master_key_mod.ENV_NAME, None)
            buf = io.StringIO()
            with redirect_stderr(buf):
                with self.assertRaises(SystemExit):
                    master_key_mod.require_credential_master_key_at_startup()
            out = buf.getvalue()
            self.assertIn(master_key_mod.ENV_NAME, out)
            self.assertIn(master_key_mod.GENERATE_HINT, out)
            # Never print a real key value.
            self.assertNotIn("os.urandom", out.split(master_key_mod.GENERATE_HINT)[0])

    def test_invalid_base64_fails(self):
        with patch.dict(
            os.environ,
            {master_key_mod.ENV_NAME: "not-valid-base64!!!", "APP_ENV": "production"},
            clear=False,
        ):
            with self.assertRaises(SystemExit):
                master_key_mod.require_credential_master_key_at_startup()

    def test_wrong_length_fails(self):
        short = base64.b64encode(os.urandom(16)).decode("ascii")
        with patch.dict(
            os.environ,
            {master_key_mod.ENV_NAME: short, "APP_ENV": "production"},
            clear=False,
        ):
            with self.assertRaises(SystemExit):
                master_key_mod.require_credential_master_key_at_startup()


class CredentialVaultCryptoTests(unittest.TestCase):
    def setUp(self):
        self.key = _ephemeral_master_key()
        self.env = patch.dict(os.environ, {master_key_mod.ENV_NAME: self.key}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_round_trip(self):
        stored = vault.encrypt_value("secret-plain", "tenant-a", "krt-1")
        self.assertEqual(vault.decrypt_value(stored, "tenant-a", "krt-1"), "secret-plain")

    def test_fresh_nonce_each_encrypt(self):
        a = vault.encrypt_value("same-password", "tenant-a", "krt-1")
        b = vault.encrypt_value("same-password", "tenant-a", "krt-1")
        self.assertNotEqual(a, b)

    def test_wrong_key_fails(self):
        stored = vault.encrypt_value("secret-plain", "tenant-a", "krt-1")
        other = _ephemeral_master_key()
        with patch.dict(os.environ, {master_key_mod.ENV_NAME: other}, clear=False):
            with self.assertRaises(vault.CredentialVaultError):
                vault.decrypt_value(stored, "tenant-a", "krt-1")

    def test_tampered_ciphertext_fails(self):
        stored = vault.encrypt_value("secret-plain", "tenant-a", "krt-1")
        raw = bytearray(base64.b64decode(stored))
        raw[-1] ^= 0x01
        tampered = base64.b64encode(bytes(raw)).decode("ascii")
        with self.assertRaises(vault.CredentialVaultError):
            vault.decrypt_value(tampered, "tenant-a", "krt-1")

    def test_wrong_tenant_binding_fails(self):
        stored = vault.encrypt_value("secret-plain", "tenant-a", "krt-1")
        with self.assertRaises(vault.CredentialVaultError):
            vault.decrypt_value(stored, "tenant-b", "krt-1")
        with self.assertRaises(vault.CredentialVaultError):
            vault.decrypt_value(stored, "tenant-a", "krt-other")


class CredentialVaultStoreTests(unittest.TestCase):
    def setUp(self):
        self.key = _ephemeral_master_key()
        self.env = patch.dict(os.environ, {master_key_mod.ENV_NAME: self.key}, clear=False)
        self.env.start()
        self.mongo = MongomockSession().start()
        database.init_db()

    def tearDown(self):
        self.mongo.stop()
        self.env.stop()

    def test_store_and_get_round_trip(self):
        vault.store_send2_credentials(
            "tenant-a",
            "krt-1",
            SAMPLE_SEND2_RESPONSE["username"],
            SAMPLE_SEND2_RESPONSE["password"],
            SAMPLE_SEND2_RESPONSE["extra"],
        )
        got = vault.get_send2_credentials("tenant-a")
        self.assertEqual(got["username"], SAMPLE_SEND2_RESPONSE["username"])
        self.assertEqual(got["password"], SAMPLE_SEND2_RESPONSE["password"])
        self.assertEqual(got["extra"], SAMPLE_SEND2_RESPONSE["extra"])

    def test_plaintext_absent_from_raw_collection(self):
        user = SAMPLE_SEND2_RESPONSE["username"]
        pwd = SAMPLE_SEND2_RESPONSE["password"]
        vault.store_send2_credentials("tenant-a", "krt-1", user, pwd, {"note": "x"})
        raw = self.mongo.database["send2_credentials"].find_one({"tenant_id": "tenant-a"})
        self.assertIsNotNone(raw)
        blob = str(raw)
        self.assertNotIn(user, blob)
        self.assertNotIn(pwd, blob)
        self.assertIn("enc_username", raw)
        self.assertIn("enc_password", raw)

    def test_sync_with_fixture_fetcher(self):
        database.create_admin(
            encode_send2_username("vault-admin-a"),
            role="admin",
            tenant_id="tenant-a",
            session_id="sess-a",
            krt_unique_id="krt-vault-demo",
        )

        def fetch(_kid):
            return dict(SAMPLE_SEND2_RESPONSE)

        result = sync_send2_credentials("tenant-a", fetch_fn=fetch)
        self.assertTrue(result["ok"])
        got = vault.get_send2_credentials("tenant-a")
        self.assertEqual(got["username"], SAMPLE_SEND2_RESPONSE["username"])

    def test_adapter_not_configured(self):
        with patch.dict(os.environ, {"SEND2_CREDENTIALS_API_URL": ""}, clear=False):
            os.environ.pop("SEND2_CREDENTIALS_API_URL", None)
            with self.assertRaises(Send2CredentialsApiNotConfigured):
                send2_fetch_credentials("krt-1")

    def test_fallback_warning_and_vault_path(self):
        vault.store_send2_credentials(
            "tenant-a", "krt-1", "vault-user", "vault-pass", {}
        )
        u, p = vault.resolve_send2_username_password("tenant-a")
        self.assertEqual((u, p), ("vault-user", "vault-pass"))

        with patch.dict(
            os.environ,
            {
                "SEND2_VAULT_FALLBACK": "true",
                "SEND2_USERNAME": "env-user",
                "SEND2_PASSWORD": "env-pass",
            },
            clear=False,
        ):
            # A tenant-scoped lookup must not borrow global .env credentials.
            with self.assertRaises(vault.CredentialVaultError):
                vault.resolve_send2_username_password("tenant-missing")

    def test_tenant_lookup_never_borrows_shared_admin_credentials(self):
        with (
            patch.dict(
                os.environ,
                {
                    "SEND2_VAULT_FALLBACK": "true",
                    "SEND2_USERNAME": "shared-user",
                    "SEND2_PASSWORD": "shared-pass",
                },
                clear=False,
            ),
            patch(
                "services.send2_accounts.credentials_from_admins",
                side_effect=lambda tenant_id=None: None,
            ) as from_admins,
        ):
            with self.assertRaises(vault.CredentialVaultError):
                vault.resolve_send2_username_password("tenant-missing")

        from_admins.assert_called_once_with("tenant-missing")

    def test_decrypt_failure_blocks_resolve(self):
        vault.store_send2_credentials("tenant-a", "krt-1", "u", "p", {})
        # Corrupt stored ciphertext
        self.mongo.database["send2_credentials"].update_one(
            {"tenant_id": "tenant-a"},
            {"$set": {"enc_password": base64.b64encode(os.urandom(40)).decode("ascii")}},
        )
        with self.assertRaises(vault.CredentialVaultError):
            vault.resolve_send2_username_password("tenant-a")


class CredentialVaultPanelAuthTests(unittest.TestCase):
    def setUp(self):
        self.key = _ephemeral_master_key()
        self.env = patch.dict(os.environ, {master_key_mod.ENV_NAME: self.key}, clear=False)
        self.env.start()
        self.mongo = MongomockSession().start()
        database.init_db()
        self.session_a = "sess-a"
        self.session_b = "sess-b"
        self.id_a = database.create_admin(
            encode_send2_username("admin-a"),
            role="admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            tenant_id="tenant-a",
            session_id=self.session_a,
            krt_unique_id="krt-a",
        )
        self.id_b = database.create_admin(
            encode_send2_username("admin-b"),
            role="admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            tenant_id="tenant-b",
            session_id=self.session_b,
            krt_unique_id="krt-b",
        )
        self.id_super = database.create_admin(
            encode_send2_username("super"),
            role="super_admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            session_id="sess-super",
        )
        vault.store_send2_credentials("tenant-a", "krt-a", "user-a", "pass-a", {})
        vault.store_send2_credentials("tenant-b", "krt-b", "user-b", "pass-b", {})
        app = FastAPI()
        app.include_router(auth_routes.router)
        app.include_router(send2_cred_routes.flat_router)
        app.include_router(send2_cred_routes.router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.mongo.stop()
        self.env.stop()

    def _headers(self, username: str, session_id: str) -> dict:
        # Panel auth is plain username + session_id (not user_id).
        return {"username": username, "session_id": session_id}

    def test_status_scoped_to_session_tenant(self):
        r = self.client.post(
            "/api/admin/tenants/send2-credentials/status",
            json={},
            headers=self._headers("admin-a", self.session_a),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["configured"])
        self.assertIsNotNone(body["last_synced_at"])
        # Never return credential values
        blob = r.text.lower()
        self.assertNotIn("pass-a", blob)
        self.assertNotIn("user-a", blob)
        self.assertNotIn("password", blob)

    def test_tenant_b_session_cannot_read_tenant_a_vault(self):
        # Session B status is for tenant-b only — never accepts a body tenant_id.
        r = self.client.post(
            "/api/admin/tenants/send2-credentials/status",
            json={"tenant_id": "tenant-a"},
            headers=self._headers("admin-b", self.session_b),
        )
        self.assertEqual(r.status_code, 200, r.text)
        # Tenant B is configured for itself; secrets still absent.
        self.assertTrue(r.json()["configured"])
        self.assertNotIn("pass-a", r.text)
        self.assertNotIn("user-a", r.text)
        # Direct vault get with wrong tenant must not return A's secrets via API —
        # there is no get-credentials endpoint. Confirm resolve by wrong tenant
        # identity is impossible through the status surface.
        got_b = vault.get_send2_credentials("tenant-b")
        self.assertEqual(got_b["username"], "user-b")
        got_a = vault.get_send2_credentials("tenant-a")
        self.assertEqual(got_a["username"], "user-a")
        self.assertNotEqual(got_a["password"], got_b["password"])

    def test_resync_requires_super_admin(self):
        denied = self.client.post(
            "/api/admin/tenants/tenant-a/send2-credentials/resync",
            json={},
            headers=self._headers("admin-a", self.session_a),
        )
        self.assertEqual(denied.status_code, 403)

        with patch(
            "routes.send2_credentials.sync_send2_credentials",
            return_value={"ok": True, "last_synced_at": "2026-01-01T00:00:00+00:00"},
        ):
            allowed = self.client.post(
                "/api/admin/tenants/tenant-a/send2-credentials/resync",
                json={},
                headers=self._headers("super", "sess-super"),
            )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertTrue(allowed.json()["ok"])
        self.assertNotIn("pass-a", allowed.text)


class CredentialLogHygieneTests(unittest.TestCase):
    def setUp(self):
        self.key = _ephemeral_master_key()
        self.env = patch.dict(os.environ, {master_key_mod.ENV_NAME: self.key}, clear=False)
        self.env.start()
        self.mongo = MongomockSession().start()
        database.init_db()
        self.password = "UniqueVaultPass-ZZ-99"
        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        logging.getLogger().addHandler(self.handler)
        logging.getLogger("credential_vault").addHandler(self.handler)
        logging.getLogger("send2_credentials_sync").addHandler(self.handler)

    def tearDown(self):
        logging.getLogger().removeHandler(self.handler)
        logging.getLogger("credential_vault").removeHandler(self.handler)
        logging.getLogger("send2_credentials_sync").removeHandler(self.handler)
        self.mongo.stop()
        self.env.stop()

    def test_password_never_appears_in_logs(self):
        vault.store_send2_credentials("tenant-log", "krt-log", "log-user", self.password, {})
        sync_send2_credentials(
            "tenant-log",
            fetch_fn=lambda _k: {
                "customer_id": "krt-log",
                "username": "log-user",
                "password": self.password,
                "extra": {},
            },
        )
        vault.get_send2_credentials("tenant-log")
        logs = self.log_stream.getvalue()
        self.assertNotIn(self.password, logs)
        self.assertEqual(logs.count(self.password), 0)


if __name__ == "__main__":
    unittest.main()
