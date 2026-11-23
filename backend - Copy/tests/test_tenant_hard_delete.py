"""Superadmin tenant delete must permanently wipe tenant-scoped DB + client pack."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mongo_test_support import MongomockSession

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
from db.mongo import Repository
from shared.tenancy import store as tenancy_store


class TenantHardDeleteTests(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        self.temp = tempfile.TemporaryDirectory()
        self.clients_root = Path(self.temp.name) / "clients"
        self.clients_root.mkdir(parents=True, exist_ok=True)
        self.clients_patch = patch("shared.tenancy.paths.CLIENTS_DIR", self.clients_root)
        self.clients_patch.start()
        database.init_db()

        self.tid = "purge-me"
        tenancy_store.ensure_tenant(
            self.tid, slug="purge-me", vertical="banking", display_name="Purge Me"
        )
        tenancy_store.save_draft(
            self.tid,
            {"display_name": "Purge Me", "brand": {"name": "Purge Me"}},
            updated_by="test",
        )
        from datetime import datetime, timezone

        Repository("products").insert(
            {"name": "Loan Pack", "slug": "loan-pack", "tenant_id": self.tid, "is_active": 1}
        )
        Repository("faq_dataset").insert(
            {
                "source_file": "kit.pdf",
                "content_type": "text",
                "content": "hello",
                "tenant_id": self.tid,
            }
        )
        Repository("customers").insert(
            {"tenant_id": self.tid, "wa_id": "919999999999", "name": "Test User"}
        )
        Repository("chat_history").insert(
            {
                "wa_id": "919999999999",
                "message": "hi",
                "response": "hello",
                "tenant_id": self.tid,
            }
        )
        Repository("app_settings").insert({"key": "active_test_tenant", "value": self.tid})
        Repository("admin_audit_events").insert(
            {
                "created_at": datetime.now(timezone.utc),
                "actor_username": "ops",
                "actor_role": "super_admin",
                "action": "tenant_created",
                "tenant_id": self.tid,
                "outcome": "success",
            }
        )

        pack = self.clients_root / self.tid
        pack.mkdir(parents=True, exist_ok=True)
        (pack / "config.json").write_text('{"tenant_id":"purge-me"}', encoding="utf-8")
        (pack / "knowledge").mkdir(exist_ok=True)

    def tearDown(self):
        self.mongo.stop()
        self.temp.cleanup()
        self.clients_patch.stop()

    def test_purge_removes_tenant_scoped_rows_and_disk_keeps_audit(self):
        summary = tenancy_store.purge_tenant_data(self.tid, slug="purge-me")

        self.assertEqual(summary["tables"].get("tenants"), 1)
        self.assertGreaterEqual(summary["tables"].get("products", 0), 1)
        self.assertGreaterEqual(summary["tables"].get("faq_dataset", 0), 1)
        self.assertGreaterEqual(summary["tables"].get("customers", 0), 1)
        self.assertGreaterEqual(summary["tables"].get("chat_history", 0), 1)
        self.assertIsNone(tenancy_store.get_tenant(self.tid))
        self.assertFalse((self.clients_root / self.tid).exists())

        self.assertEqual(Repository("products").count({"tenant_id": self.tid}), 0)
        self.assertEqual(Repository("faq_dataset").count({"tenant_id": self.tid}), 0)
        self.assertEqual(Repository("customers").count({"tenant_id": self.tid}), 0)
        self.assertEqual(
            Repository("draft_config").count({"scope": tenancy_store.profile_scope(self.tid)}),
            0,
        )
        self.assertIsNone(Repository("app_settings").find_one({"key": "active_test_tenant"}))
        # Prior audit history for this tenant is retained.
        self.assertEqual(
            Repository("admin_audit_events").count({"tenant_id": self.tid}),
            1,
        )


if __name__ == "__main__":
    unittest.main()
