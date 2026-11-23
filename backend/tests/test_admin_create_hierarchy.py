"""Superadmin → admin only; admin → sub_admin only; many admins per tenant."""

import os
import sys
import unittest
from unittest.mock import patch

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
from routes import auth as auth_routes
from routes import tenants as tenants_routes


def _headers(username: str, session_id: str) -> dict:
    return {"username": username, "session_id": session_id}


class AdminCreateHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        self.resolver_patch = patch(
            "shared.tenancy.resolver.resolve_default_tenant", return_value="default"
        )
        self.resolver_patch.start()
        database.init_db()

        self.app = FastAPI()
        self.app.include_router(auth_routes.router)
        self.app.include_router(tenants_routes.router)
        self.client = TestClient(self.app, raise_server_exceptions=False)

        self.root_session = "root-session"
        database.create_admin(
            encode_send2_username("root"),
            role="super_admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            session_id=self.root_session,
        )
        self.root = _headers("root", self.root_session)

        created = self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "acme",
                "vertical": "generic",
                "display_name": "Acme Ltd",
                "mobile_number": "+91 98765 43210",
            },
            headers=self.root,
        )
        self.assertEqual(created.status_code, 200, created.text)

        self.admin_session = "acme-admin-session"
        database.create_admin(
            encode_send2_username("acme-admin"),
            role="admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            tenant_id="acme",
            session_id=self.admin_session,
        )
        self.acme_admin = _headers("acme-admin", self.admin_session)

    def tearDown(self):
        self.mongo.stop()
        self.resolver_patch.stop()

    def test_multiple_company_admins_share_tenant(self):
        second = self.client.post(
            "/api/auth/create",
            json={"username": "acme-admin-2", "role": "admin", "tenant_id": "acme"},
            headers=self.root,
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["role"], "admin")
        self.assertEqual(second.json()["tenant_id"], "acme")
        self.assertEqual(database.count_tenant_admins("acme"), 2)

    def test_super_admin_cannot_create_sub_admin(self):
        refused = self.client.post(
            "/api/auth/create",
            json={"username": "nope-sub", "role": "sub_admin", "tenant_id": "acme"},
            headers=self.root,
        )
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertIn("company admins only", refused.json()["detail"])

    def test_company_admin_cannot_create_admin(self):
        refused = self.client.post(
            "/api/auth/create",
            json={"username": "nope-admin", "role": "admin", "tenant_id": "acme"},
            headers=self.acme_admin,
        )
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertIn("sub-admins only", refused.json()["detail"])

    def test_company_admin_creates_sub_admin(self):
        created = self.client.post(
            "/api/auth/create",
            json={"username": "helper", "role": "sub_admin"},
            headers=self.acme_admin,
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["role"], "sub_admin")
        self.assertEqual(created.json()["tenant_id"], "acme")


if __name__ == "__main__":
    unittest.main()
