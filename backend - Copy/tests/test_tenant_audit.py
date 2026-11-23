"""Tenant mutation audit attribution.

Mongo writes are not wrapped in a SQL transaction. An audit insert failure
after ``ensure_tenant`` leaves the tenant row in place.
"""

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

from fastapi import BackgroundTasks

from db.mongo import Repository
from routes import tenants


class TenantAuditTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        self.resolver_patch = patch(
            "shared.tenancy.resolver.resolve_default_tenant", return_value="default"
        )
        self.resolver_patch.start()
        self.admin = {"id": 1, "username": "root", "role": "super_admin", "tenant_id": None}

    def tearDown(self):
        self.mongo.stop()
        self.resolver_patch.stop()

    def test_tenant_creation_records_actor_and_tenant(self):
        body = tenants.TenantCreate(
            tenant_id="tenant-new", slug="new", vertical="generic",
            display_name="New", mobile_number="919800000010",
        )
        with patch.object(tenants.tenancy_cache, "purge"), patch("shared.tenancy.loader.build_profile", return_value={}):
            result = tenants.create_tenant(body, BackgroundTasks(), current_admin=self.admin)
        self.assertEqual(result["tenant"]["id"], "tenant-new")
        row = Repository("admin_audit_events").find_one({"action": "tenant_created"})
        self.assertIsNotNone(row)
        self.assertEqual(
            (row["actor_username"], row["actor_role"], row["tenant_id"], row["action"]),
            ("root", "super_admin", "tenant-new", "tenant_created"),
        )

    def test_tenant_creation_does_not_roll_back_when_audit_insert_fails(self):
        body = tenants.TenantCreate(
            tenant_id="tenant-new", slug="new", vertical="generic",
            display_name="New", mobile_number="919800000011",
        )
        with patch.object(tenants.tenancy_cache, "purge"), \
             patch("shared.tenancy.loader.build_profile", return_value={}), \
             patch.object(tenants, "record_admin_audit_event", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                tenants.create_tenant(body, BackgroundTasks(), current_admin=self.admin)
        # The mongo path writes the tenant before the audit call and has no
        # surrounding transaction, so the registry row remains.
        self.assertIsNotNone(Repository("tenants").find_one({"id": "tenant-new"}))


if __name__ == "__main__":
    unittest.main()
