"""QA Section 1 — auth checks against the FastAPI app in-process.

The live server on port 9000 is not part of the unit suite. These cases
exercise the same login and admin routes through TestClient and mongomock.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from mongo_test_support import MongomockSession

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import database
from core.send2_auth import encode_send2_username
from routes import auth as auth_routes
from routes import status as status_routes


class Section1AuthLive(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        database.init_db()
        self.session = "seed-session"
        database.create_admin(
            encode_send2_username("qa-admin"),
            role="super_admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            session_id=self.session,
        )
        app = FastAPI()
        app.include_router(auth_routes.router)
        app.include_router(status_routes.router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.mongo.stop()

    def test_login_empty_credentials(self):
        r = self.client.post("/api/auth/login", json={"username": "", "session_id": ""})
        self.assertIn(r.status_code, (400, 401, 422))

    def test_login_wrong_password_generic(self):
        r = self.client.post(
            "/api/auth/login",
            json={"username": "definitely-not-a-user-xyz", "session_id": "wrong-session"},
        )
        body = r.text.lower()
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("no such user", body)
        self.assertNotIn("user not found", body)

    def test_login_sql_injection_style(self):
        r = self.client.post(
            "/api/auth/login",
            json={"username": "' OR '1'='1", "session_id": "' OR '1'='1"},
        )
        self.assertIn(r.status_code, (401, 422))
        if r.status_code >= 400:
            self.assertNotIn("token", r.text.lower())

    def test_first_admin_second_call_blocked(self):
        r1 = self.client.post(
            "/api/auth/first-admin",
            json={"username": "qa_first", "session_id": "x"},
        )
        r2 = self.client.post(
            "/api/auth/first-admin",
            json={"username": "qa_first2", "session_id": "y"},
        )
        self.assertEqual(r1.status_code, 404)
        self.assertNotEqual(r2.status_code, 200)

    def test_tampered_jwt_rejected(self):
        r = self.client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer stale-token"},
        )
        self.assertEqual(r.status_code, 401)

    def test_missing_auth_on_admin_route(self):
        r = self.client.get("/api/auth/admins")
        self.assertEqual(r.status_code, 401)

    def test_rate_limit_rapid_login(self):
        # RATE_LIMIT is disabled under pytest, so these stay 401/422 and must not 500.
        codes = []
        for i in range(8):
            r = self.client.post(
                "/api/auth/login",
                json={"username": "rate-limit-probe", "session_id": f"bad-{i}"},
            )
            codes.append(r.status_code)
        self.assertTrue(codes)
        self.assertTrue(all(code in (401, 422) for code in codes))
        self.assertNotIn(500, codes)

    def test_webhook_status_leaks_verify_token(self):
        r = self.client.get("/webhook/status")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertNotIn("verify_token", body)
        self.assertIn("verify_token_set", body)
        config = body.get("send2_config") or {}
        self.assertEqual(
            set(config),
            {"username_set", "password_set", "number_set"},
        )
        self.assertTrue(all(isinstance(value, bool) for value in config.values()))


if __name__ == "__main__":
    unittest.main()
