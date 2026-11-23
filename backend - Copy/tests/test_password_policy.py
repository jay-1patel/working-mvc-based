"""Session credentials replace passwords: login, create, and session rotation."""

import json
import os
import sys
import unittest

from mongo_test_support import MongomockSession

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.testclient import TestClient

import database
from core.send2_auth import encode_send2_username
from db.mongo import Repository
from routes import auth as auth_routes


class SessionCredentialTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        database.init_db()
        self.app = FastAPI()
        if auth_routes.RATE_LIMIT_ENABLED:
            self.app.state.limiter = auth_routes.limiter
        self.app.include_router(auth_routes.router)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.session = "root-session-secret"
        database.create_admin(
            encode_send2_username("root"),
            role="super_admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            session_id=self.session,
            email="root@example.com",
        )
        self.headers = {"username": "root", "session_id": self.session}

    def tearDown(self):
        self.mongo.stop()

    def test_missing_session_id_is_422(self):
        res = self.client.post("/api/auth/login", json={"username": "root"})
        self.assertEqual(res.status_code, 422)

    def test_wrong_session_is_generic_401_without_enumeration(self):
        wrong = self.client.post(
            "/api/auth/login",
            json={"username": "root", "session_id": "not-the-session"},
        )
        unknown = self.client.post(
            "/api/auth/login",
            json={"username": "nobody-xyz", "session_id": "not-the-session"},
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json()["detail"], unknown.json()["detail"])
        self.assertNotIn("user not found", wrong.text.lower())
        self.assertNotIn("not-the-session", wrong.text)

    def test_base64_username_is_rejected(self):
        encoded = encode_send2_username("root")
        res = self.client.post(
            "/api/auth/login",
            json={"username": encoded, "session_id": self.session},
        )
        self.assertEqual(res.status_code, 401)
        self.assertNotIn(self.session, res.text)
        self.assertNotIn("user not found", res.text.lower())

    def test_seeded_admin_can_login(self):
        res = self.client.post(
            "/api/auth/login",
            json={"username": "root", "session_id": self.session},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["username"], "root")
        self.assertEqual(body["session_id"], self.session)
        self.assertEqual(body["role"], "super_admin")
        self.assertIn("token", body)

    def test_create_returns_session_id_that_authenticates(self):
        made = self.client.post(
            "/api/auth/create",
            json={"username": "helper", "role": "admin", "email": "helper@example.com"},
            headers=self.headers,
        )
        self.assertEqual(made.status_code, 200, made.text)
        session_id = made.json()["session_id"]
        self.assertTrue(session_id)
        login = self.client.post(
            "/api/auth/login",
            json={"username": "helper", "session_id": session_id},
        )
        self.assertEqual(login.status_code, 200, login.text)
        me = self.client.get(
            "/api/auth/me",
            headers={"username": "helper", "session_id": session_id},
        )
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["username"], "helper")

    def test_regenerate_session_invalidates_the_old_session(self):
        made = self.client.post(
            "/api/auth/create",
            json={"username": "helper", "role": "admin"},
            headers=self.headers,
        )
        self.assertEqual(made.status_code, 200, made.text)
        old = made.json()["session_id"]
        regen = self.client.post(
            "/api/auth/admins/helper/regenerate-session",
            headers=self.headers,
        )
        self.assertEqual(regen.status_code, 200, regen.text)
        new = regen.json()["session_id"]
        self.assertNotEqual(new, old)
        stale = self.client.post(
            "/api/auth/login",
            json={"username": "helper", "session_id": old},
        )
        self.assertEqual(stale.status_code, 401)
        self.assertNotIn(old, stale.text)
        fresh = self.client.post(
            "/api/auth/login",
            json={"username": "helper", "session_id": new},
        )
        self.assertEqual(fresh.status_code, 200, fresh.text)

    def test_audit_and_login_errors_do_not_echo_the_session_secret(self):
        secret = "supplied-session-secret-xyz"
        failed = self.client.post(
            "/api/auth/login",
            json={"username": "root", "session_id": secret},
        )
        self.assertEqual(failed.status_code, 401)
        self.assertNotIn(secret, failed.text)
        blob = json.dumps(Repository("admin_audit_events").find_all(), default=str)
        self.assertNotIn(secret, blob)
        self.assertNotIn("password", blob.lower())


if __name__ == "__main__":
    unittest.main()
