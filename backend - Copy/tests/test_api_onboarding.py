"""Coverage for tenant API onboarding requests and superadmin review."""

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
from db.mongo import Repository
from routes import api_onboarding
from shared.tenancy import store as tenancy_store


class ApiOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        self.resolver_patch = patch(
            "shared.tenancy.resolver.resolve_default_tenant", return_value="default"
        )
        self.resolver_patch.start()
        database.init_db()
        for tid in ("tenant-a", "tenant-b"):
            tenancy_store.ensure_tenant(
                tid, slug=tid, vertical="generic", display_name=tid, status="active"
            )

        self.client = TestClient(FastAPI())
        self.client.app.include_router(api_onboarding.router)
        self.current_admin = None

        def _current_admin():
            return self.current_admin

        self.client.app.dependency_overrides[api_onboarding.get_current_admin] = _current_admin

    def tearDown(self):
        self.mongo.stop()
        self.resolver_patch.stop()

    @staticmethod
    def _admin(tenant_id="tenant-a", role="admin", **permissions):
        return {
            "id": 4 if role != "super_admin" else 1,
            "username": "tenant-user" if role != "super_admin" else "root",
            "role": role,
            "tenant_id": tenant_id,
            "permissions": {"manage_operations": True, **permissions},
        }

    def _create(self, api_type="payment_api", purpose="Reconcile settled payments", **extra):
        return self.client.post(
            "/api/integration-requests",
            json={
                "api_type": api_type,
                "provider": "Acme Gateway",
                "environment": "sandbox",
                "purpose": purpose,
                **extra,
            },
        )

    def _events(self, **filters):
        return Repository("api_onboarding_request_events").find_all(
            filters or None, sort=[("id", 1)]
        )

    def test_schema_initialization_is_repeatable(self):
        database.init_db()
        database.init_db()
        names = set(self.mongo.database.list_collection_names())
        self.assertIn("api_onboarding_requests", names)
        self.assertIn("api_onboarding_request_events", names)
        self.assertIn("api_onboarding_entitlements", names)

    def test_submitter_tenant_is_derived_and_requests_are_tenant_scoped(self):
        self.current_admin = self._admin()
        created = self._create()
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["request"]["tenant_id"], "tenant-a")
        self.assertEqual(created.json()["request"]["status"], "pending")

        mine = self.client.get("/api/integration-requests")
        self.assertEqual(len(mine.json()["requests"]), 1)
        self.current_admin = self._admin("tenant-b")
        self.assertEqual(self.client.get("/api/integration-requests").json()["requests"], [])

        events = self._events()
        self.assertEqual(
            [(row["event_type"], row["new_status"]) for row in events],
            [("submitted", "pending")],
        )

    def test_submit_requires_tenant_role_and_permission(self):
        self.current_admin = self._admin(None)
        self.assertEqual(self._create().status_code, 403)

        self.current_admin = {**self._admin(), "permissions": {"manage_operations": False}}
        self.assertEqual(self._create().status_code, 403)

        self.current_admin = self._admin(None, role="super_admin")
        self.assertEqual(self._create().status_code, 403)

    def test_only_one_pending_or_approved_request_per_tenant_and_api(self):
        self.current_admin = self._admin()
        self.assertEqual(self._create().status_code, 201)
        self.assertEqual(self._create().status_code, 409)

        self.current_admin = self._admin(None, role="super_admin")
        approved = self.client.post(
            "/api/admin/integration-requests/1/decision",
            json={"decision": "approved", "note": "Eligible for secure setup"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["request"]["status"], "approved")
        self.current_admin = self._admin()
        self.assertEqual(self._create().status_code, 409)

    def test_only_superadmin_can_list_review_queue_and_decide(self):
        self.current_admin = self._admin()
        self.assertEqual(self._create().status_code, 201)
        self.assertEqual(self.client.get("/api/admin/integration-requests").status_code, 403)
        self.assertEqual(
            self.client.post("/api/admin/integration-requests/1/decision", json={"decision": "approved"}).status_code,
            403,
        )

        self.current_admin = self._admin(None, role="super_admin")
        self.assertEqual(len(self.client.get("/api/admin/integration-requests").json()["requests"]), 1)
        result = self.client.post(
            "/api/admin/integration-requests/1/decision",
            json={"decision": "rejected", "note": "Not supported yet"},
        ).json()["request"]
        self.assertEqual(result["reviewer_username"], "root")
        self.assertEqual(result["decision_note"], "Not supported yet")
        self.assertIsNotNone(result["decided_at"])

        event = self._events(event_type="decision")[0]
        self.assertEqual(
            (event["actor_role"], event["old_status"], event["new_status"], event["note"]),
            ("super_admin", "pending", "rejected", "Not supported yet"),
        )

    def test_decision_is_one_time_and_rejected_request_can_be_resubmitted(self):
        self.current_admin = self._admin()
        self._create()
        self.current_admin = self._admin(None, role="super_admin")
        decision = {"decision": "rejected"}
        self.assertEqual(self.client.post("/api/admin/integration-requests/1/decision", json=decision).status_code, 200)
        self.assertEqual(self.client.post("/api/admin/integration-requests/1/decision", json=decision).status_code, 409)
        self.current_admin = self._admin()
        self.assertEqual(self._create().status_code, 201)

    def test_approval_grants_entitlement_and_rejection_does_not(self):
        self.current_admin = self._admin()
        self._create()
        self.current_admin = self._admin(None, role="super_admin")
        response = self.client.post("/api/admin/integration-requests/1/decision", json={"decision": "approved"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["request"]["eligible"])
        events = self.client.get("/api/admin/integration-requests/1/events").json()["events"]
        self.assertEqual([event["event_type"] for event in events], ["submitted", "decision"])

    def test_invalid_fields_types_and_likely_secrets_are_rejected_without_echo(self):
        self.current_admin = self._admin()
        self.assertEqual(self._create(api_key="sensitive-value").status_code, 422)
        secret = "sk_live_sensitive-value"
        response = self._create(purpose=f"Use {secret} to reconcile settled payments")
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(secret, response.text)
        self.assertEqual(self._create(api_type="unknown").status_code, 422)


if __name__ == "__main__":
    unittest.main()
