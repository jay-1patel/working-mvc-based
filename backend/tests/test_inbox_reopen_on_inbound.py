"""Inbound messages must reopen resolved conversations in the live inbox."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

from mongo_test_support import MongomockSession

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
from db.conversations_ops import tenant_inbox_queue
from db.mongo import Repository
from shared.tenancy import cache as tenancy_cache
from shared.tenancy import store as tenancy_store


TENANT = "inbox-reopen-test"
WA = "919512777899"


class InboxReopenOnInboundTest(unittest.TestCase):
    def setUp(self):
        self.mongo = MongomockSession().start()
        database.init_db()
        tenancy_store.ensure_tenant(
            TENANT, vertical="generic", display_name="Inbox Reopen Test"
        )
        tenancy_cache.purge(TENANT)
        Repository("user_states").upsert(
            {"tenant_id": TENANT, "wa_id": WA},
            {
                "tenant_id": TENANT,
                "wa_id": WA,
                "human_handover": 0,
                "handover_resolved_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        Repository("chat_history").insert(
            {
                "tenant_id": TENANT,
                "wa_id": WA,
                "sender_name": "Customer",
                "message": "hi",
                "route": "greeting",
                "created_at": datetime.now(timezone.utc),
            }
        )

    def tearDown(self):
        self.mongo.stop()
        tenancy_cache.purge(TENANT)

    def test_resolved_chat_hidden_until_reopened(self):
        hidden = tenant_inbox_queue(TENANT, include_resolved=False)
        self.assertFalse(
            any(c.get("wa_id") == WA for c in hidden.get("conversations") or [])
        )

        ok = database.reopen_conversation_on_inbound(WA, TENANT)
        self.assertTrue(ok)

        state = Repository("user_states").find_one({"tenant_id": TENANT, "wa_id": WA})
        self.assertIsNotNone(state)
        self.assertFalse(state.get("handover_resolved_at"))

        shown = tenant_inbox_queue(TENANT, include_resolved=False)
        self.assertTrue(
            any(c.get("wa_id") == WA for c in shown.get("conversations") or [])
        )

    def test_include_resolved_keeps_chat_and_marks_state(self):
        shown = tenant_inbox_queue(TENANT, include_resolved=True)
        row = next(c for c in shown.get("conversations") or [] if c.get("wa_id") == WA)
        self.assertTrue(row.get("resolved"))

    def test_set_human_handover_active_clears_resolved(self):
        database.set_human_handover(WA, True, tenant_id=TENANT)
        state = Repository("user_states").find_one({"tenant_id": TENANT, "wa_id": WA})
        self.assertEqual(state.get("human_handover"), 1)
        self.assertFalse(state.get("handover_resolved_at"))


if __name__ == "__main__":
    unittest.main()
