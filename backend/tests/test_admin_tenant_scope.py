"""Tenant isolation tests for the Team & Manage admin APIs."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from mongo_test_support import MongomockSession

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
from core.send2_auth import encode_send2_username
from fastapi import HTTPException
from routes import auth


class AdminTenantScopeTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        database.init_db()
        self._create_admin("admin-a", "admin", "tenant-a")
        self._create_admin("sub-a", "sub_admin", "tenant-a")
        self._create_admin("admin-b", "admin", "tenant-b")
        self._create_admin("sub-b", "sub_admin", "tenant-b")

    def tearDown(self):
        self.mongo.stop()

    @staticmethod
    def _admin(username, role, tenant_id):
        return {
            "username": username,
            "role": role,
            "tenant_id": tenant_id,
            "permissions": {"manage_admins": True},
        }

    def _create_admin(self, username, role, tenant_id, session_id=None):
        return database.create_admin(
            username=encode_send2_username(username),
            role=role,
            permissions={"manage_admins": True},
            tenant_id=tenant_id,
            session_id=session_id or f"session-{username}",
        )

    def _record(self, username):
        return database.get_admin_record(encode_send2_username(username))

    def test_tenant_admin_list_is_scoped_and_unassigned_fails_closed(self):
        listed = auth.list_admins(current_admin=self._admin("admin-a", "admin", "tenant-a"))
        self.assertEqual({row["username"] for row in listed["admins"]}, {"admin-a", "sub-a"})
        self.assertEqual(
            auth.list_admins(current_admin=self._admin("root", "admin", None))["admins"],
            [],
        )

    def test_tenant_admin_cannot_update_delete_or_reset_other_tenant(self):
        actor = self._admin("admin-a", "admin", "tenant-a")
        with self.assertRaises(HTTPException) as update_error:
            auth.update_admin("sub-b", auth.UpdateAdminRequest(email="changed@example.test"), actor)
        self.assertEqual(update_error.exception.status_code, 404)

        with self.assertRaises(HTTPException) as delete_error:
            auth.delete_admin_endpoint("sub-b", actor)
        self.assertEqual(delete_error.exception.status_code, 404)

        victim_session = self._record("sub-b")["session_id"]
        # regenerate-session allows another admin only when the caller is a
        # super admin. A tenant admin targeting a different tenant is refused
        # before the row is touched, so the victim session stays put.
        with self.assertRaises(HTTPException) as reset_error:
            auth.regenerate_admin_session("sub-b", actor)
        self.assertIn(reset_error.exception.status_code, (403, 404))
        self.assertEqual(self._record("sub-b")["session_id"], victim_session)
        self.assertIsNone(self._record("sub-b")["email"])

    def test_same_tenant_management_and_super_admin_global_access(self):
        actor = self._admin("admin-a", "admin", "tenant-a")
        updated = auth.update_admin("sub-a", auth.UpdateAdminRequest(email="new@example.test"), actor)
        self.assertEqual(updated["username"], "sub-a")
        self.assertEqual(self._record("sub-a")["email"], "new@example.test")

        before = self._record("sub-a")["session_id"]
        regenerated = auth.regenerate_admin_session("sub-a", self._admin("sub-a", "sub_admin", "tenant-a"))
        self.assertNotEqual(regenerated["session_id"], before)
        self.assertEqual(self._record("sub-a")["session_id"], regenerated["session_id"])

        root = self._admin("root", "super_admin", None)
        self.assertEqual(
            {row["username"] for row in auth.list_admins(current_admin=root)["admins"]},
            {"admin-a", "sub-a", "admin-b", "sub-b"},
        )
        # D-05 (QA 2026-11-13): a super admin is view-only inside tenants, so
        # administratively modifying a TENANT-bound account is refused even
        # for the super admin; their global access covers platform-level
        # accounts (no tenant binding) instead.
        with self.assertRaises(HTTPException) as update_error:
            auth.update_admin("sub-b", auth.UpdateAdminRequest(email="root@example.test"), root)
        self.assertEqual(update_error.exception.status_code, 403)
        self.assertIsNone(self._record("sub-b")["email"])

        self._create_admin("platform-op", "admin", None)
        auth.update_admin(
            "platform-op", auth.UpdateAdminRequest(email="root@example.test"), root
        )
        self.assertEqual(
            self._record("platform-op")["email"], "root@example.test"
        )


if __name__ == "__main__":
    unittest.main()
