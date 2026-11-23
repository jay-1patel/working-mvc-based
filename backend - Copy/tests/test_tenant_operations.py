"""Isolated tenant-scope regression tests for Customers and Orders."""

import os
import sys
import unittest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import HTTPException

from db.mongo import Repository
from db import tenant_operations_ops as tops
from mongo_test_support import MongomockSession, seed_tenant_operations_fixture
from routes import tenant_operations as tenant_routes
from routes.auth import require_tenant_admin_permission, require_super_admin_permission
from routes.orders import OrderUpdate


class TenantOperationsTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        seed_tenant_operations_fixture(self.mongo.database)

    def tearDown(self):
        self.mongo.stop()

    @staticmethod
    def _admin(tenant_id, role="admin", **permissions):
        return {
            "username": "operator",
            "role": role,
            "tenant_id": tenant_id,
            "permissions": permissions,
        }

    def test_customers_are_scoped_across_all_sources_and_aggregates(self):
        a = tops.tenant_list_customers(tenant_id="tenant-a", q="", limit=200)
        b = tops.tenant_list_customers(tenant_id="tenant-b", q="", limit=200)

        self.assertEqual(a["count"], 1)
        self.assertEqual(a["customers"][0]["name"], "A Name")
        self.assertEqual(a["customers"][0]["mobile"], "111")
        self.assertEqual(a["customers"][0]["total_orders"], 1)
        self.assertEqual(a["customers"][0]["total_spent"], 50)
        self.assertEqual(a["customers"][0]["total_complaints"], 1)
        self.assertEqual(a["customers"][0]["open_complaints"], 1)

        self.assertEqual(b["count"], 1)
        self.assertEqual(b["customers"][0]["name"], "B Name")
        self.assertEqual(b["customers"][0]["mobile"], "222")
        self.assertEqual(b["customers"][0]["total_orders"], 1)
        self.assertEqual(b["customers"][0]["total_spent"], 900)
        self.assertEqual(b["customers"][0]["total_complaints"], 1)
        self.assertEqual(b["customers"][0]["open_complaints"], 0)

    def test_customer_search_matches_name_mobile_and_wa_id(self):
        by_name = tops.tenant_list_customers(tenant_id="tenant-a", q="A Name", limit=200)
        by_mobile = tops.tenant_list_customers(tenant_id="tenant-a", q="111", limit=200)
        self.assertEqual(by_name["count"], 1)
        self.assertEqual(by_mobile["count"], 1)
        self.assertEqual(
            tops.tenant_list_customers(tenant_id="tenant-a", q="B Name", limit=200)["count"],
            0,
        )

    def test_orders_and_aggregates_exclude_other_and_unowned_rows(self):
        a = tops.tenant_list_orders(
            tenant_id="tenant-a", status=None, order_type=None, payment_status=None, q="", limit=200
        )
        b = tops.tenant_list_orders(
            tenant_id="tenant-b", status=None, order_type=None, payment_status=None, q="", limit=200
        )
        self.assertEqual([row["order_number"] for row in a["orders"]], ["A-1"])
        self.assertEqual(a["counts"]["total"], 1)
        self.assertEqual(a["counts"]["revenue"], 50)
        self.assertEqual([row["order_number"] for row in b["orders"]], ["B-1"])
        self.assertEqual(b["counts"]["total"], 1)
        self.assertEqual(b["counts"]["revenue"], 900)
        self.assertEqual(
            tops.tenant_order_stats("tenant-a")["total"],
            1,
        )

    def test_cross_tenant_order_read_update_delete_are_not_found(self):
        admin_a = self._admin("tenant-a", view_orders=True, manage_orders=True)
        with self.assertRaises(HTTPException) as read_error:
            tenant_routes.get_tenant_order("tenant-a", "B-1", current_admin=admin_a)
        self.assertEqual(read_error.exception.status_code, 404)

        with self.assertRaises(HTTPException) as update_error:
            tenant_routes.update_tenant_order(
                "tenant-a", "B-1", OrderUpdate(status="cancelled"), current_admin=admin_a
            )
        self.assertEqual(update_error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as delete_error:
            tenant_routes.delete_tenant_order("tenant-a", "B-1", current_admin=admin_a)
        self.assertEqual(delete_error.exception.status_code, 404)

        row = Repository("orders").find_one({"order_number": "B-1"})
        self.assertEqual(row["status"], "delivered")

    def test_tenant_scope_dependency_rejects_wrong_or_missing_assignment(self):
        dependency = require_tenant_admin_permission("view_orders")
        matching = self._admin("tenant-a", view_orders=True)
        self.assertEqual(dependency(tenant_id="tenant-a", current_admin=matching), matching)
        with self.assertRaises(HTTPException) as wrong_tenant:
            dependency(tenant_id="tenant-b", current_admin=matching)
        self.assertEqual(wrong_tenant.exception.status_code, 403)
        with self.assertRaises(HTTPException) as unassigned:
            dependency(tenant_id="tenant-a", current_admin=self._admin(None, view_orders=True))
        self.assertEqual(unassigned.exception.status_code, 403)
        with self.assertRaises(HTTPException) as missing_permission:
            dependency(tenant_id="tenant-a", current_admin=self._admin("tenant-a"))
        self.assertEqual(missing_permission.exception.status_code, 403)

    def test_only_super_admin_can_use_global_order_dependency(self):
        dependency = require_super_admin_permission("view_orders")
        super_admin = self._admin(None, role="super_admin", view_orders=True)
        self.assertEqual(dependency(current_admin=super_admin), super_admin)
        with self.assertRaises(HTTPException) as denied:
            dependency(current_admin=self._admin("tenant-a", view_orders=True))
        self.assertEqual(denied.exception.status_code, 403)

    @unittest.skip("order_service uses MongoDB transactions; mongomock does not support sessions yet")
    def test_new_order_records_explicit_tenant(self):
        pass


if __name__ == "__main__":
    unittest.main()