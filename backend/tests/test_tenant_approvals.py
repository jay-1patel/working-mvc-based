"""Coverage for tenant change requests.

Signup / registration credentials mean the company is already approved —
``create_tenant`` and profile publishes apply immediately (no super-admin gate).
"""

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

from fastapi import FastAPI
from fastapi.testclient import TestClient

import database
from core.send2_auth import encode_send2_username
from routes import auth as auth_routes
from routes import tenant_approvals
from routes import tenants as tenants_routes
from shared.tenancy import store as tenancy_store


def _headers(user_id: int | str, session_id: str) -> dict:
    return {"user_id": str(user_id), "session_id": session_id}


class TenantApprovalTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        self.resolver_patch = patch(
            "shared.tenancy.resolver.resolve_default_tenant", return_value="default"
        )
        self.resolver_patch.start()
        database.init_db()

        self.app = FastAPI()
        if auth_routes.RATE_LIMIT_ENABLED:
            self.app.state.limiter = auth_routes.limiter
        self.app.include_router(auth_routes.router)
        self.app.include_router(tenants_routes.router)
        self.app.include_router(tenant_approvals.router)
        self.client = TestClient(self.app)

        self.root_session = "root-session"
        root_id = database.create_admin(
            encode_send2_username("root"),
            role="super_admin",
            permissions=dict(auth_routes.SUPER_ADMIN_PERMISSIONS),
            session_id=self.root_session,
        )
        self.root = _headers(root_id, self.root_session)

    def tearDown(self):
        self.mongo.stop()
        self.resolver_patch.stop()

    # ── helpers ────────────────────────────────────────────────────────

    def _create_admin(self, username, role="admin", tenant_id=None, *, creator=None):
        # Mirrors the Team screen's payload: explicit nulls for permissions
        # (admins get the server default), email and unused tenant scope.
        # Superadmin creates company admins; only a company admin creates sub-admins.
        payload = {
            "username": username,
            "role": role,
            "permissions": None,
            "email": None,
            "tenant_id": tenant_id if role != "sub_admin" else None,
        }
        headers = creator if creator is not None else self.root
        res = self.client.post(
            "/api/auth/create",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 200, res.text
        payload = res.json()
        return _headers(payload["user_id"] or payload["id"], payload["session_id"])

    def _submit_create(self, headers, tenant_id="acme", **extra):
        return self.client.post(
            "/api/tenant-change-requests",
            json={
                "request_type": "create_tenant",
                "tenant_id": tenant_id,
                "tenant": {
                    "slug": tenant_id,
                    "vertical": "generic",
                    "display_name": "Acme Ltd",
                    "waba_phone_id": "",
                    "mobile_number": "919800000001",
                    "status": "active",
                },
                "snapshot": {},
                **extra,
            },
            headers=headers,
        )

    def _submit_publish(self, headers, tenant_id):
        return self.client.post(
            "/api/tenant-change-requests",
            json={"request_type": "publish_profile", "tenant_id": tenant_id},
            headers=headers,
        )

    def _decide(self, request_id, decision, note=""):
        return self.client.post(
            f"/api/admin/tenant-change-requests/{request_id}/decision",
            json={"decision": decision, "note": note},
            headers=self.root,
        )

    def _current_version(self, tenant_id):
        res = self.client.get("/api/admin/tenants", headers=self.root)
        for row in res.json()["tenants"]:
            if row["id"] == tenant_id:
                return row["current_version"]
        return None

    # ── registration flow ──────────────────────────────────────────────

    def test_admin_can_create_tenants_and_publish_directly(self):
        # Registration and publish both go live immediately — no approval gate.
        admin = self._create_admin("plain-admin")
        created = self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "acme",
                "vertical": "generic",
                "mobile_number": "919800000021",
                "auto_scrape": False,
            },
            headers=admin,
        )
        self.assertEqual(created.status_code, 200)
        self.assertIsNotNone(tenancy_store.get_tenant("acme"))

        # A draft missing the compulsory contact fields is refused outright.
        tenancy_store.save_draft("acme", {})
        res = self.client.post("/api/admin/tenants/acme/publish", headers=admin)
        self.assertEqual(res.status_code, 422)
        self.assertIn("Missing required profile fields", res.json()["detail"])

        tenancy_store.save_draft(
            "acme",
            {"brand": {"support_email": "care@acme.example", "support_phone": "+91 98765 43210"}},
        )
        res = self.client.post("/api/admin/tenants/acme/publish", headers=admin)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body.get("ok"), True)
        self.assertEqual(body.get("version"), 1)
        self.assertEqual(self._current_version("acme"), 1)

        # A super admin is view-only inside a tenant and cannot publish.
        tenancy_store.save_draft(
            "acme",
            {"brand": {"support_email": "care@acme.example", "support_phone": "+91 98765 43210"}},
        )
        direct_pub = self.client.post(
            "/api/admin/tenants/acme/publish", headers=self.root
        )
        self.assertEqual(direct_pub.status_code, 403)
        self.assertEqual(self._current_version("acme"), 1)

    def test_menu_only_publish_goes_live_immediately(self):
        """Menu / intent edits publish directly without super-admin approval."""
        admin = self._create_admin("menu-admin")
        self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "acme",
                "vertical": "generic",
                "mobile_number": "919800000041",
                "auto_scrape": False,
            },
            headers=self.root,
        )
        # Seed a live baseline so a menu-only diff is possible.
        tenancy_store.save_draft(
            "acme",
            {
                "brand": {
                    "support_email": "care@acme.example",
                    "support_phone": "+91 98765 43210",
                },
                "menu": {"buttons": [{"id": "help", "title": "Help"}]},
            },
        )
        # Super admin cannot publish via API; bootstrap live version via store.
        tenancy_store.publish_version(
            "acme",
            tenancy_store.get_draft("acme"),
            published_by="root",
        )
        self.assertEqual(self._current_version("acme"), 1)

        tenancy_store.save_draft(
            "acme",
            {
                "brand": {
                    "support_email": "care@acme.example",
                    "support_phone": "+91 98765 43210",
                },
                "menu": {"buttons": [{"id": "help", "title": "Get help"}]},
            },
        )
        res = self.client.post("/api/admin/tenants/acme/publish", headers=admin)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body.get("ok"), True)
        self.assertEqual(body.get("version"), 2)
        self.assertEqual(self._current_version("acme"), 2)

    # ── contact-detail validation ───────────────────────────────

    def test_registration_rejects_invalid_contact_details(self):
        admin = self._create_admin("contact-admin")
        # Phone without a country code.
        res = self._submit_create(
            admin, snapshot={"brand": {"support_phone": "9876543210"}}
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("country code", res.json()["detail"])
        # Website that is not a URL.
        res = self._submit_create(
            admin, snapshot={"brand": {"website": "not a website"}}
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("website URL", res.json()["detail"])
        # Email that is not an email.
        res = self._submit_create(
            admin, snapshot={"notifications": {"sales_email": "nope"}}
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("email address", res.json()["detail"])
        # waba_phone_id must be digits only.
        res = self.client.post(
            "/api/tenant-change-requests",
            json={
                "request_type": "create_tenant",
                "tenant_id": "acme",
                "tenant": {
                    "slug": "acme",
                    "vertical": "generic",
                    "display_name": "Acme Ltd",
                    "waba_phone_id": "12345",
                    "mobile_number": "919800000001",
                    "status": "active",
                },
            },
            headers=admin,
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("10-16 digits", res.json()["detail"])
        # Valid contact details queue fine.
        res = self._submit_create(
            admin,
            snapshot={
                "brand": {
                    "website": "https://acme.example",
                    "support_email": "care@acme.example",
                    "support_phone": "+91 98765 43210",
                }
            },
        )
        self.assertEqual(res.status_code, 201)

    def test_profile_rejects_invalid_contact_details(self):
        admin = self._create_admin("profile-admin")
        self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "acme",
                "vertical": "generic",
                "mobile_number": "919800000031",
                "auto_scrape": False,
            },
            headers=self.root,
        )
        # Saving a broken draft is allowed; the problem comes back as a
        # validation warning.
        res = self.client.post(
            "/api/admin/tenants/acme/profile",
            json={"snapshot": {"brand": {"website": "not a url"}}},
            headers=admin,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any("website URL" in w for w in res.json()["validation"]))
        # A publish of that draft is refused outright instead of queueing.
        res = self.client.post("/api/admin/tenants/acme/publish", headers=admin)
        self.assertEqual(res.status_code, 422)
        # Fix the contact details and the publish goes live immediately.
        res = self.client.post(
            "/api/admin/tenants/acme/profile",
            json={
                "snapshot": {
                    "brand": {
                        "website": "https://acme.example",
                        "support_email": "care@acme.example",
                        "support_phone": "+91 98765 43210",
                    }
                }
            },
            headers=admin,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["validation"], [])
        res = self.client.post("/api/admin/tenants/acme/publish", headers=admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("ok"), True)
        self.assertEqual(res.json().get("version"), 1)

    def test_registration_submission_applies_immediately(self):
        admin = self._create_admin("reg-admin")
        created = self._submit_create(admin)
        self.assertEqual(created.status_code, 201)
        request = created.json()["request"]
        self.assertEqual(request["status"], "approved")
        self.assertEqual(request["tenant_id"], "acme")
        self.assertEqual(request["applied_version"], 1)
        self.assertIsNotNone(tenancy_store.get_tenant("acme"))
        self.assertEqual(self._current_version("acme"), 1)

        # Tenant already exists — a second create conflicts at submit time.
        self.assertEqual(self._submit_create(admin).status_code, 409)

        # The admin sees their own submission.
        mine = self.client.post("/api/tenant-change-requests/mine", headers=admin, json={})
        self.assertEqual([r["id"] for r in mine.json()["requests"]], [request["id"]])

        # Super admins do not submit via the change-request queue.
        self.assertEqual(self._submit_create(self.root).status_code, 403)
        self.assertEqual(
            self.client.get(
                "/api/admin/tenant-change-requests", headers=admin
            ).status_code,
            403,
        )

        events = self.client.get(
            f"/api/admin/tenant-change-requests/{request['id']}/events",
            headers=self.root,
        ).json()["events"]
        self.assertEqual([e["event_type"] for e in events], ["submitted", "decision"])

        # Already applied — cannot decide again.
        self.assertEqual(self._decide(request["id"], "rejected").status_code, 409)

    def test_registration_conflicts_when_tenant_already_exists(self):
        admin = self._create_admin("reg-admin-2")
        # Super admin registers the id first.
        self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "acme",
                "vertical": "generic",
                "mobile_number": "919800000032",
                "auto_scrape": False,
            },
            headers=self.root,
        )
        conflict = self._submit_create(admin, tenant_id="acme")
        self.assertEqual(conflict.status_code, 409)

    def test_registration_creates_tenant_on_submit(self):
        admin = self._create_admin("reg-admin-3")
        created = self._submit_create(admin, tenant_id="ghost")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["request"]["status"], "approved")
        self.assertIsNotNone(tenancy_store.get_tenant("ghost"))
        self.assertEqual(self._current_version("ghost"), 1)

    # ── publish flow ────────────────────────────────────────────────────

    def _register_tenant(self, tenant_id="acme"):
        mobiles = {
            "acme": "919800000040",
            "ghost": "919800000041",
        }
        res = self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": tenant_id,
                "vertical": "generic",
                "mobile_number": mobiles.get(tenant_id, "919800000049"),
                "auto_scrape": False,
            },
            headers=self.root,
        )
        assert res.status_code == 200, res.text

    def test_publish_submission_requires_tenant_and_draft(self):
        admin = self._create_admin("pub-admin")
        self.assertEqual(self._submit_publish(admin, "nope").status_code, 404)

        self._register_tenant()
        self.assertEqual(self._submit_publish(admin, "acme").status_code, 400)

        tenancy_store.save_draft(
            "acme",
            {"brand": {"name": "Acme", "support_email": "care@acme.example", "support_phone": "+91 98765 43210"}},
        )
        submitted = self._submit_publish(admin, "acme")
        self.assertEqual(submitted.status_code, 201)
        self.assertEqual(submitted.json()["request"]["status"], "pending")
        self.assertEqual(self._submit_publish(admin, "acme").status_code, 409)

    def test_publish_is_tenant_scoped_and_applies_submitted_snapshot(self):
        self._register_tenant("acme")
        tenancy_store.save_draft(
            "acme",
            {"brand": {"name": "Acme", "support_email": "care@acme.example", "support_phone": "+91 98765 43210"}},
        )

        # One admin per company: the cross-tenant scoping check uses a
        # sub admin created by that admin (superadmin cannot create sub-admins).
        scoped = self._create_admin("scoped-admin", tenant_id="acme")
        other = self._create_admin("other-sub", role="sub_admin", creator=scoped)
        self._register_tenant("rival")
        self.assertEqual(self._submit_publish(other, "rival").status_code, 403)

        created = self._submit_publish(scoped, "acme")
        self.assertEqual(created.status_code, 201)
        request_id = created.json()["request"]["id"]

        # The draft keeps moving after submission; approval applies the
        # snapshot captured at submission time, not the newer one.
        tenancy_store.save_draft("acme", {"brand": {"name": "Moved On"}})

        approved = self._decide(request_id, "approved")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(self._current_version("acme"), 1)

        from shared.tenancy.loader import get_tenant_profile

        profile = get_tenant_profile("acme")
        self.assertEqual(profile.brand.name, "Acme")

    # ── the split registration flow ─────────────────────────────────────

    def test_superadmin_registers_company_admin_completes_and_publishes(self):
        """Super admin registers the company; the admin fills details and
        publishes immediately — no approval gate."""
        # 1. Super admin creates the tenant with the company basics only.
        created = self.client.post(
            "/api/admin/tenants",
            json={
                "tenant_id": "acme",
                "vertical": "generic",
                "display_name": "Acme Ltd",
                "mobile_number": "919800000098",
                "auto_scrape": False,
            },
            headers=self.root,
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(self._current_version("acme"), 0)

        # 2. Admin fills WhatsApp onwards: binds the phone, saves the draft.
        admin = self._create_admin("completer")
        snapshot = {
            "display_name": "Acme Ltd",
            "brand": {
                "name": "Acme Ltd",
                "bot_name": "Asha",
                "support_email": "care@acme.example",
                "support_phone": "+91 98765 43210",
            },
            "business_hours": {"timezone": "Asia/Kolkata", "always_open": True},
        }
        bound = self.client.post(
            "/api/admin/tenants/acme/phone-id",
            json={"waba_phone_id": "100012345678901"},
            headers=admin,
        )
        self.assertEqual(bound.status_code, 200)
        saved = self.client.post(
            "/api/admin/tenants/acme/profile",
            json={"snapshot": snapshot},
            headers=admin,
        )
        self.assertEqual(saved.status_code, 200)

        # 3. Admin publish goes live immediately.
        published = self.client.post("/api/admin/tenants/acme/publish", headers=admin)
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(self._current_version("acme"), 1)

        from shared.tenancy.loader import get_tenant_profile

        profile = get_tenant_profile("acme")
        self.assertEqual(profile.brand.bot_name, "Asha")

        # The registry picked up the admin's phone binding too.
        tenant_row = tenancy_store.get_tenant("acme")
        self.assertEqual(tenant_row["waba_phone_id"], "100012345678901")

    def test_publish_applies_immediately_via_change_request(self):
        self._register_tenant("acme")
        tenancy_store.save_draft(
            "acme",
            {"brand": {"name": "Acme", "support_email": "care@acme.example", "support_phone": "+91 98765 43210"}},
        )

        scoped = self._create_admin("scoped-admin-2", tenant_id="acme")
        first = self._submit_publish(scoped, "acme")
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["request"]["status"], "approved")
        self.assertEqual(self._current_version("acme"), 1)

        tenancy_store.save_draft(
            "acme",
            {"brand": {"name": "Changed", "support_email": "care@acme.example", "support_phone": "+91 98765 43210"}},
        )
        second = self._submit_publish(scoped, "acme")
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["request"]["status"], "approved")
        self.assertEqual(self._current_version("acme"), 2)

        from shared.tenancy.loader import get_tenant_profile

        self.assertEqual(get_tenant_profile("acme").brand.name, "Changed")


if __name__ == "__main__":
    unittest.main()
