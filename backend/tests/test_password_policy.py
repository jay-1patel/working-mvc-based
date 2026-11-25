"""Session credentials replace passwords: login, create, and session rotation."""

import json
import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for path in (BACKEND_DIR, PROJECT_ROOT, TESTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mongo_test_support import MongomockSession
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
        self.root_id = database.create_admin(
            encode_send2_username("root"),
            role="super_admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            session_id=self.session,
            email="root@example.com",
        )
        self.headers = {"user_id": str(self.root_id), "session_id": self.session}

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
            json={"username": "nobody-here", "session_id": "not-the-session"},
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json()["detail"], unknown.json()["detail"])
        self.assertNotIn("user not found", wrong.text.lower())
        self.assertNotIn("not-the-session", wrong.text)

    def test_user_id_login_is_rejected(self):
        res = self.client.post(
            "/api/auth/login",
            json={"user_id": self.root_id, "session_id": self.session},
        )
        self.assertEqual(res.status_code, 422)
        self.assertNotIn("token", res.text.lower())

    def test_seeded_admin_can_login(self):
        res = self.client.post(
            "/api/auth/login",
            json={"username": "root", "session_id": self.session},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["username"], "root")
        self.assertEqual(body["user_id"], self.root_id)
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
        payload = made.json()
        session_id = payload["session_id"]
        user_id = payload["user_id"] or payload["id"]
        self.assertTrue(session_id)
        self.assertTrue(user_id)
        login = self.client.post(
            "/api/auth/login",
            json={"username": "helper", "session_id": session_id},
        )
        self.assertEqual(login.status_code, 200, login.text)
        me = self.client.get(
            "/api/auth/me",
            headers={"user_id": str(user_id), "session_id": session_id},
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
        user_id = made.json()["user_id"] or made.json()["id"]
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
