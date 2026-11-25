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
        """Request without user_id & session_id headers must return 401."""
        resp = self.client.post("/api/auth/privileges")
        self.assertEqual(resp.status_code, 401)

    def test_privileges_super_admin_view_only(self):
        """Super admin must have is_tenant_view_only=True and can_write=False on tenant pages."""
        plain = "superadmin_test"
        encoded = encode_send2_username(plain)
        session_id = "super-sess-123"
        user_id = 9001

        row = {
            "id": user_id,
            "username": encoded,
            "session_id": session_id,
            "role": "super_admin",
            "permissions": auth_routes.SUPER_ADMIN_PERMISSIONS,
            "tenant_id": None,
        }

        with patch.object(auth_routes, "get_admin_by_id", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"user_id": str(user_id), "session_id": session_id},
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
        user_id = 9002

        row = {
            "id": user_id,
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }

        with patch.object(auth_routes, "get_admin_by_id", return_value=row), \
             patch.object(
                 auth_routes,
                 "_fetch_tenant_features",
                 return_value={"human_handover": True, "kb": True, "faq": True},
             ):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"user_id": str(user_id), "session_id": session_id},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], plain)
        self.assertEqual(data["role"], "admin")
        self.assertFalse(data["is_tenant_view_only"])
        self.assertEqual(data["tenant_id"], "c")

        pages = data["pages"]
        self.assertTrue(pages["chats"]["can_write"])
        self.assertTrue(pages["chats"]["actions"]["reply"])
        self.assertTrue(pages["profile"]["can_write"])
        self.assertTrue(pages["upload"]["can_write"])
        self.assertTrue(pages["menu"]["can_write"])

    def test_privileges_body_auth(self):
        """Authenticate when user_id + session_id are provided only in JSON body."""
        plain = "body_admin"
        encoded = encode_send2_username(plain)
        session_id = "body-sess"
        user_id = 9003
        row = {
            "id": user_id,
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }
        with patch.object(auth_routes, "get_admin_by_id", return_value=row), \
             patch.object(auth_routes, "_fetch_tenant_features", return_value={}):
            resp = self.client.post(
                "/api/auth/privileges",
                json={"user_id": user_id, "session_id": session_id},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], plain)

    def test_privileges_header_and_body_auth(self):
        """Authenticate when user_id + session_id are in both headers and body."""
        plain = "both_admin"
        encoded = encode_send2_username(plain)
        session_id = "both-sess"
        user_id = 9004
        row = {
            "id": user_id,
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }
        with patch.object(auth_routes, "get_admin_by_id", return_value=row), \
             patch.object(auth_routes, "_fetch_tenant_features", return_value={}):
            resp = self.client.post(
                "/api/auth/privileges",
                headers={"user_id": str(user_id), "session_id": session_id},
                json={"user_id": user_id, "session_id": session_id},
            )
        self.assertEqual(resp.status_code, 200)

    def test_privileges_raw_json_without_content_type(self):
        plain = "raw_admin"
        encoded = encode_send2_username(plain)
        session_id = "raw-sess"
        user_id = 9005
        row = {
            "id": user_id,
            "username": encoded,
            "session_id": session_id,
            "role": "admin",
            "permissions": {k: True for k in auth_routes.ALL_PERMISSIONS},
            "tenant_id": "c",
        }
        with patch.object(auth_routes, "get_admin_by_id", return_value=row), \
             patch.object(auth_routes, "_fetch_tenant_features", return_value={}):
            resp = self.client.post(
                "/api/auth/privileges",
                content=json.dumps({"user_id": user_id, "session_id": session_id}),
            )
        self.assertEqual(resp.status_code, 200)

    def test_privileges_wrong_session(self):
        plain = "wrong_sess"
        encoded = encode_send2_username(plain)
        user_id = 9006
        row = {
            "id": user_id,
            "username": encoded,
            "session_id": "real-session",
            "role": "admin",
            "permissions": {},
            "tenant_id": "c",
        }
        with patch.object(auth_routes, "get_admin_by_id", return_value=row):
            resp = self.client.post(
                "/api/auth/privileges",
                json={"user_id": user_id, "session_id": "wrong-session"},
            )
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
