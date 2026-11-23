import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.send2_auth import encode_send2_username
from routes import auth as auth_routes


class PrivilegesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(auth_routes.router)
        cls.client = TestClient(cls.app)

    def test_privileges_requires_post_method(self):
        """GET /api/auth/privileges must return 405 Method Not Allowed."""
        resp = self.client.get("/api/auth/privileges")
        self.assertEqual(resp.status_code, 405)

    def test_privileges_unauthenticated(self):
        """Request without username & session_id headers must return 401."""
        resp = self.client.post("/api/auth/privileges")
        self.assertEqual(resp.status_code, 401)

    def test_privileges_super_admin_view_only(self):
        """Super admin must have is_tenant_view_only=True and can_write=False on tenant pages."""
        plain = "superadmin_test"
        encoded = encode_send2_username(plain)
        session_id = "super-sess-123"

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "super_admin",
            "permissions": auth_routes.SUPER_ADMIN_PERMISSIONS,
            "tenant_id": None,
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"username": plain, "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], plain)
        self.assertEqual(data["role"], "super_admin")
        self.assertTrue(data["is_tenant_view_only"])

        pages = data["pages"]
        for page in ("chats", "dashboard", "profile", "upload", "menu"):
            self.assertIn(page, pages)

        self.assertTrue(pages["chats"]["accessible"])
        self.assertTrue(pages["chats"]["can_read"])
        self.assertFalse(pages["chats"]["can_write"])
        self.assertFalse(pages["chats"]["actions"]["reply"])
        self.assertFalse(pages["chats"]["actions"]["handover"])
        self.assertFalse(pages["chats"]["actions"]["assign"])
        self.assertFalse(pages["chats"]["actions"]["resolve"])
        self.assertFalse(pages["chats"]["actions"]["send_attachment"])

        self.assertTrue(pages["dashboard"]["accessible"])
        self.assertTrue(pages["dashboard"]["can_read"])
        self.assertFalse(pages["dashboard"]["can_write"])
        self.assertTrue(pages["dashboard"]["actions"]["view_overview"])
        self.assertTrue(pages["dashboard"]["actions"]["view_analytics"])
        self.assertTrue(pages["dashboard"]["actions"]["view_errors"])

        self.assertTrue(pages["profile"]["accessible"])
        self.assertTrue(pages["profile"]["can_read"])
        self.assertFalse(pages["profile"]["can_write"])
        self.assertTrue(pages["profile"]["actions"]["view_profile"])
        self.assertFalse(pages["profile"]["actions"]["edit_profile"])
        self.assertFalse(pages["profile"]["actions"]["publish_profile"])

        self.assertTrue(pages["upload"]["accessible"])
        self.assertTrue(pages["upload"]["can_read"])
        self.assertFalse(pages["upload"]["can_write"])
        self.assertTrue(pages["upload"]["actions"]["view_files"])
        self.assertFalse(pages["upload"]["actions"]["upload_kb"])
        self.assertFalse(pages["upload"]["actions"]["upload_faq"])
        self.assertFalse(pages["upload"]["actions"]["delete_files"])
        self.assertFalse(pages["upload"]["actions"]["catalogue_new_arrival"])

        self.assertTrue(pages["menu"]["accessible"])
        self.assertTrue(pages["menu"]["can_read"])
        self.assertFalse(pages["menu"]["can_write"])
        self.assertTrue(pages["menu"]["actions"]["view_menu"])
        self.assertFalse(pages["menu"]["actions"]["edit_menu"])
        self.assertFalse(pages["menu"]["actions"]["publish_menu"])
        self.assertFalse(pages["menu"]["actions"]["add_product"])
        self.assertFalse(pages["menu"]["actions"]["edit_product"])
        self.assertFalse(pages["menu"]["actions"]["delete_product"])

    def test_privileges_admin_full_access(self):
        """Admin must have is_tenant_view_only=False and can_write=True for permitted actions."""
        plain = "cars_admin"
        encoded = encode_send2_username(plain)
        session_id = "admin-sess-456"

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row), \
             patch.object(
                 auth_routes,
                 "_fetch_tenant_features",
                 return_value={"human_handover": True, "kb": True, "faq": True},
             ):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"username": plain, "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], plain)
        self.assertEqual(data["role"], "admin")
        self.assertEqual(data["tenant_id"], "c")
        self.assertFalse(data["is_tenant_view_only"])
        self.assertEqual(data["features"]["human_handover"], True)

        pages = data["pages"]
        self.assertTrue(pages["chats"]["accessible"])
        self.assertTrue(pages["chats"]["can_read"])
        self.assertTrue(pages["chats"]["can_write"])
        self.assertTrue(pages["chats"]["actions"]["reply"])
        self.assertTrue(pages["chats"]["feature_flags"]["human_handover"])

        self.assertTrue(pages["dashboard"]["accessible"])
        self.assertFalse(pages["dashboard"]["can_write"])
        self.assertFalse(pages["dashboard"]["actions"]["view_errors"])

        self.assertTrue(pages["profile"]["accessible"])
        self.assertTrue(pages["profile"]["can_write"])
        self.assertTrue(pages["profile"]["actions"]["edit_profile"])
        self.assertTrue(pages["profile"]["actions"]["publish_profile"])

        self.assertTrue(pages["upload"]["accessible"])
        self.assertTrue(pages["upload"]["can_write"])
        self.assertTrue(pages["upload"]["actions"]["upload_kb"])
        self.assertTrue(pages["upload"]["actions"]["upload_faq"])
        self.assertTrue(pages["upload"]["actions"]["delete_files"])
        self.assertTrue(pages["upload"]["feature_flags"]["kb"])

        self.assertTrue(pages["menu"]["accessible"])
        self.assertTrue(pages["menu"]["can_write"])
        self.assertTrue(pages["menu"]["actions"]["edit_menu"])
        self.assertTrue(pages["menu"]["actions"]["publish_menu"])
        self.assertTrue(pages["menu"]["actions"]["add_product"])

    def test_privileges_sub_admin_selective_permissions(self):
        """Sub admin with only support permissions should have limited page access."""
        plain = "support_agent"
        encoded = encode_send2_username(plain)
        session_id = "sub-sess-789"

        sub_perms = {
            "view_inbox": True,
            "chat_history": True,
            "chat": True,
            "manage_complaints": True,
            "view_complaints": True,
            "view_files": False,
            "upload_kb": False,
            "upload_faq": False,
            "delete_files": False,
            "manage_operations": False,
            "view_products": False,
            "edit_delete_products": False,
        }

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "sub_admin",
            "permissions": sub_perms,
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row), \
             patch.object(auth_routes, "_fetch_tenant_features", return_value={"human_handover": True}):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"username": plain, "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], plain)
        self.assertEqual(data["role"], "sub_admin")
        self.assertFalse(data["is_tenant_view_only"])

        pages = data["pages"]
        self.assertTrue(pages["chats"]["accessible"])
        self.assertTrue(pages["chats"]["can_read"])
        self.assertTrue(pages["chats"]["can_write"])
        self.assertTrue(pages["chats"]["actions"]["reply"])

        self.assertFalse(pages["upload"]["accessible"])
        self.assertFalse(pages["upload"]["can_read"])
        self.assertFalse(pages["upload"]["can_write"])

        self.assertFalse(pages["menu"]["accessible"])
        self.assertFalse(pages["menu"]["can_read"])
        self.assertFalse(pages["menu"]["can_write"])

        self.assertTrue(pages["profile"]["accessible"])
        self.assertFalse(pages["profile"]["can_write"])
        self.assertFalse(pages["profile"]["actions"]["edit_profile"])

    def test_existing_me_endpoint_unaffected(self):
        """GET /api/auth/me continues to work identically."""
        plain = "cars"
        encoded = encode_send2_username(plain)
        session_id = "sess-me-check"

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {"view_inbox": True},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row), \
             patch.object(auth_routes, "_onboarding_approved", return_value=True):
            resp = self.client.get(
                "/api/auth/me",
                headers={"username": plain, "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], plain)
        self.assertEqual(data["role"], "admin")
        self.assertEqual(data["tenant_id"], "c")
        self.assertTrue(data["permissions"]["view_inbox"])
        self.assertFalse(data["permissions"]["upload_faq"])
        self.assertTrue(data["onboarding_approved"])

    def test_privileges_auth_from_json_body_only(self):
        """Authenticate when username + session_id are provided only in JSON body."""
        plain = "cars_body_only"
        encoded = encode_send2_username(plain)
        session_id = "body-sess-111"

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                json={"username": plain, "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], plain)
        self.assertEqual(data["role"], "admin")
        self.assertIn("pages", data)

    def test_privileges_auth_from_both_headers_and_body(self):
        """Authenticate when username + session_id are in both headers and body."""
        plain = "cars_both"
        encoded = encode_send2_username(plain)
        session_id = "both-sess-222"

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"username": plain, "session_id": session_id},
                json={"username": plain, "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], plain)

    def test_privileges_auth_from_raw_data_body(self):
        """Authenticate when raw JSON is sent via content without Content-Type."""
        plain = "cars_raw_data"
        encoded = encode_send2_username(plain)
        session_id = "raw-sess-333"

        row = {
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                content=json.dumps({"username": plain, "session_id": session_id}),
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], plain)

    def test_privileges_invalid_credentials_in_body(self):
        """Invalid credentials in JSON body must return 401 Invalid credentials."""
        plain = "cars_invalid"
        encoded = encode_send2_username(plain)

        row = {
            "username": encoded,
            "session_id": "correct-session",
            "role": "admin",
            "permissions": {},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_username", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                json={"username": plain, "session_id": "wrong-session"},
            )

        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid credentials", resp.json().get("detail", ""))

    def test_privileges_empty_body_and_no_headers(self):
        """Empty JSON body and no headers must return 401 with standard detail."""
        resp = self.client.post("/api/auth/privileges", json={})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Not authenticated", resp.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
