"""Tests for durable admin audit history."""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from db.mongo import Repository
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
from routes import audit, auth


def _parse_created_at(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.fromisoformat(value.replace(" ", "T") + "+00:00")


class AuditHistoryTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        database.init_db()
        self.staff_session = "staff-live-session"
        Repository("admins").insert(
            {
                "username": encode_send2_username("staff"),
                "role": "sub_admin",
                "permissions": {"manage_operations": True},
                "tenant_id": "tenant-a",
                "session_id": self.staff_session,
            }
        )

        self.current_admin = {"id": 1, "username": "root", "role": "super_admin", "tenant_id": None}
        app = FastAPI()
        app.include_router(audit.router)
        app.include_router(auth.router)

        def _current_admin():
            # Look up the attribute at call time so tests can reassign the actor.
            return self.current_admin

        app.dependency_overrides[audit.get_current_admin] = _current_admin
        self.client = TestClient(app)

    def tearDown(self):
        self.mongo.stop()

    def _insert(self, *, action, actor="staff", role="sub_admin", outcome="success", tenant="tenant-a", details=None, created_at="2026-10-07 12:00:00"):
        Repository("admin_audit_events").insert(
            {
                "created_at": _parse_created_at(created_at),
                "actor_id": 2,
                "actor_username": actor,
                "actor_role": role,
                "action": action,
                "outcome": outcome,
                "resource_type": "tenant",
                "resource_id": "tenant-a",
                "tenant_id": tenant,
                "details_json": details or {},
            }
        )

    @unittest.skip("SQLite DDL idempotency/retention test removed for MongoDB-only backend")
    def test_schema_initialization_is_idempotent_and_prunes_old_events(self):
        conn = self._connect()
        conn.execute(
            "INSERT INTO admin_audit_events (created_at, action) VALUES ('2024-01-01 00:00:00', 'old')"
        )
        conn.commit()
        database._init_admin_audit_tables(conn)
        database._init_admin_audit_tables(conn)
        count = conn.execute("SELECT COUNT(*) FROM admin_audit_events").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    @unittest.skip("SQLite transaction atomicity test removed for MongoDB-only backend")
    def test_event_write_is_atomic_with_mutation(self):
        conn = self._connect()
        conn.execute("CREATE TABLE audit_test_mutations (id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()
        conn = self._connect()
        conn.execute("BEGIN")
        conn.execute("INSERT INTO audit_test_mutations (id, value) VALUES (1, 'changed')")
        with patch.object(database, "safe_audit_details", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                database.record_admin_audit_event(conn, action="test_mutation", actor=self.current_admin)
        conn.rollback()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_test_mutations").fetchone()[0], 0)
        conn.close()

    def test_audit_endpoint_roles(self):
        # Sub admins are refused. A tenant admin is allowed but scoped to
        # their own tenant (role-panels item 12); super admins see all.
        self.current_admin = {"id": 2, "username": "staff", "role": "sub_admin", "tenant_id": "tenant-a"}
        response = self.client.get("/api/admin/audit-history")
        self.assertEqual(response.status_code, 403)
        self.current_admin = {"id": 2, "username": "staff", "role": "admin", "tenant_id": "tenant-a"}
        response = self.client.get("/api/admin/audit-history")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/admin/audit-history", params={"tenant_id": "tenant-b"})
        self.assertEqual(response.status_code, 403)

    def test_filters_and_pagination_return_safe_event_fields(self):
        self._insert(action="login", outcome="failure", details={"reason": "invalid_credentials"})
        self._insert(action="tenant_profile_published", details={"version": 3}, created_at="2026-10-06 12:00:00")
        self._insert(action="tenant_deleted", actor="another", tenant="tenant-b", created_at="2026-10-05 12:00:00")

        response = self.client.get(
            "/api/admin/audit-history",
            params={"action": "login", "outcome": "failure", "tenant_id": "tenant-a", "limit": 1},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["events"][0]["action"], "login")
        self.assertEqual(payload["events"][0]["details"], {"reason": "invalid_credentials"})
        self.assertNotIn("details_json", payload["events"][0])

        search = self.client.get("/api/admin/audit-history", params={"search": "published", "start_date": "2026-10-06", "end_date": "2026-10-06"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["total"], 1)

    def test_actor_filter_matches_partial_username(self):
        self._insert(action="login", actor="leewayadmin")
        self._insert(action="login", actor="otheruser")

        partial = self.client.get("/api/admin/audit-history", params={"actor": "lee"})
        self.assertEqual(partial.status_code, 200)
        payload = partial.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["events"][0]["actor_username"], "leewayadmin")

        # Stuck pagination past the filtered total must not hide matches that exist on page 1.
        empty_page = self.client.get(
            "/api/admin/audit-history",
            params={"actor": "lee", "limit": 50, "offset": 50},
        )
        self.assertEqual(empty_page.status_code, 200)
        self.assertEqual(empty_page.json()["total"], 1)
        self.assertEqual(empty_page.json()["events"], [])

    def test_invalid_date_range_and_outcome_are_rejected(self):
        self.assertEqual(
            self.client.get("/api/admin/audit-history", params={"start_date": "2026-10-08", "end_date": "2026-10-07"}).status_code,
            422,
        )
        self.assertEqual(self.client.get("/api/admin/audit-history", params={"outcome": "maybe"}).status_code, 422)

    def test_first_admin_creation_is_audited_without_password_material(self):
        missing = self.client.post(
            "/api/auth/first-admin",
            json={"username": "bootstrap", "session_id": "no-such-route"},
        )
        self.assertEqual(missing.status_code, 404)
        again = self.client.post(
            "/api/auth/first-admin",
            json={"username": "bootstrap-2", "session_id": "still-missing"},
        )
        self.assertNotEqual(again.status_code, 200)

        database.create_admin(
            encode_send2_username("root"),
            role="super_admin",
            permissions=dict(auth.SUPER_ADMIN_PERMISSIONS),
            session_id="root-session",
        )
        created = self.client.post(
            "/api/auth/create",
            json={"username": "bootstrap", "role": "admin", "email": "root@example.test"},
            headers={"username": "root", "session_id": "root-session"},
        )
        # The dependency override authenticates as the seeded super admin.
        self.assertEqual(created.status_code, 200, created.text)
        session_id = created.json()["session_id"]
        events = Repository("admin_audit_events").find_all(
            {"action": "admin_created"}, sort=[("id", -1)], limit=1
        )
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["action"], "admin_created")
        blob = json.dumps(event.get("details_json") or {}, default=str)
        self.assertNotIn("password", blob.lower())
        self.assertNotIn(session_id, blob)

    def test_login_success_and_failure_are_recorded_without_credentials(self):
        wrong_session = "wrong-session-secret"
        failed = self.client.post(
            "/api/auth/login",
            json={"username": "staff", "session_id": wrong_session},
        )
        success = self.client.post(
            "/api/auth/login",
            json={"username": "staff", "session_id": self.staff_session},
        )
        self.assertEqual(failed.status_code, 401)
        self.assertEqual(success.status_code, 200, success.text)

        rows = Repository("admin_audit_events").find_all(sort=[("id", 1)])
        self.assertEqual(
            [(row["action"], row["outcome"]) for row in rows],
            [("login", "failure"), ("login", "success")],
        )
        self.assertEqual(rows[0]["actor_username"], "staff")
        self.assertEqual(rows[0]["tenant_id"], "tenant-a")
        blob = json.dumps(rows, default=str)
        self.assertNotIn(wrong_session, blob)
        self.assertNotIn(self.staff_session, blob)

    def test_login_succeeds_without_jwt_and_bearer_alone_is_rejected(self):
        client = TestClient(self.client.app, raise_server_exceptions=False)
        self.client.app.dependency_overrides.pop(auth.get_current_admin, None)
        response = client.post(
            "/api/auth/login",
            json={"username": "staff", "session_id": self.staff_session},
        )
        token_response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer stale-token"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("jwt", response.text.lower())
        self.assertEqual(token_response.status_code, 401)

    def test_admin_update_records_changed_fields_and_role_change_is_refused(self):
        # Roles are fixed at account creation (role-panels item 10): a PATCH
        # that tries to change the role is refused and changes nothing,
        # while a permissions edit still applies and is audited.
        # The actor is the TENANT's own admin: since D-05 (QA 2026-11-13) a
        # super admin is view-only inside tenants and may not administer
        # tenant-bound accounts at all.
        self.current_admin = {
            "id": 3, "username": "tenant-admin", "role": "admin", "tenant_id": "tenant-a",
            "permissions": {"manage_admins": True},
        }
        refused = self.client.patch("/api/auth/admins/staff", json={"role": "admin"})
        response = self.client.patch(
            "/api/auth/admins/staff", json={"permissions": {"view_customers": True}}
        )
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(response.status_code, 200, response.text)
        row = Repository("admin_audit_events").find_all(sort=[("id", -1)], limit=1)[0]
        updated = Repository("admins").find_one({"username": encode_send2_username("staff")})
        self.assertEqual(updated["role"], "sub_admin")
        self.assertEqual(row["action"], "admin_updated")
        details = row.get("details_json") or {}
        self.assertEqual(details["role_before"], "sub_admin")
        self.assertEqual(details["role_after"], "sub_admin")
        self.assertIn("permissions", details["changed_fields"])

    def test_login_history_is_available_through_superadmin_endpoint(self):
        self._insert(action="login", outcome="failure")
        response = self.client.get("/api/admin/audit-history", params={"category": "authentication"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["events"][0]["outcome"], "failure")

    def test_sensitive_detail_keys_are_removed(self):
        event_id = database.record_admin_audit_event(
            None,
            action="test_redaction",
            actor=self.current_admin,
            details={"changed_fields": ["role"], "password": "never-store", "nested": {"token": "never-store"}},
        )
        row = Repository("admin_audit_events").find_one({"id": event_id})
        details = row.get("details_json") or {}
        self.assertEqual(details, {"changed_fields": ["role"], "nested": {}})
        self.assertNotIn("never-store", json.dumps(details))

    def test_audit_context_captures_ip_user_agent_and_safe_tenant_metadata(self):
        Repository("tenants").insert(
            {"id": "tenant-a", "display_name": "Leeway Softech", "slug": "leeway"}
        )

        database.set_audit_request_context(ip_address="203.0.113.9", user_agent="AuditTest/1")
        event_id = database.record_admin_audit_event(
            None,
            action="file_uploaded",
            actor={"id": 3, "username": "uploader", "role": "admin", "tenant_id": "tenant-a"},
            tenant_id="tenant-a",
            details={"file_name": "services.pdf", "file_path": "C:\\private\\services.pdf", "source_url": "https://example.test/signed?secret=x"},
        )
        row = Repository("admin_audit_events").find_one({"id": event_id})
        database.clear_audit_request_context()
        self.assertEqual(row["ip_address"], "203.0.113.9")
        self.assertEqual(row["user_agent"], "AuditTest/1")
        self.assertEqual(row["tenant_name"], "Leeway Softech")
        self.assertEqual(row["tenant_slug"], "leeway")
        details = row.get("details_json") or {}
        self.assertEqual(details, {"file_name": "services.pdf"})
        self._insert(action="legacy_sensitive", details={"auth_token_value": "legacy-secret", "visible": "safe"})
        response = self.client.get("/api/admin/audit-history", params={"action": "legacy_sensitive"})
        self.assertNotIn("legacy-secret", response.text)
        self.assertEqual(response.json()["events"][0]["details"], {"visible": "safe"})


if __name__ == "__main__":
    unittest.main()
