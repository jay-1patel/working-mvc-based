"""Isolated mongomock wiring for backend unit tests (MongoDB-only backend)."""

from __future__ import annotations

try:
    import conftest  # noqa: F401 — ensures tests/ + backend/ on sys.path
except ImportError:
    pass

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mongomock

from db.mongo import Repository, initialize_indexes

_HELLO = {"setName": "rs0", "isWritablePrimary": True}


class MongomockSession:
    """Patch ``db.mongo`` (and ``database`` re-exports) to an isolated mongomock DB."""

    def __init__(self, db_name: str | None = None) -> None:
        self.db_name = db_name or f"unittest_{uuid.uuid4().hex[:12]}"
        self.client: mongomock.MongoClient | None = None
        self.database = None
        self._patches: list = []
        self._admin_patch = None

    def start(self) -> MongomockSession:
        self.client = mongomock.MongoClient(tz_aware=True)
        self.database = self.client[self.db_name]

        def _admin_command(cmd, *args, **kwargs):
            if cmd in ("hello", "isMaster", "ismaster"):
                return dict(_HELLO)
            if cmd == "isWritablePrimary":
                return True
            raise NotImplementedError(f"unmocked admin command: {cmd!r}")

        self._patches = [
            patch("db.mongo.get_client", return_value=self.client),
            patch("db.mongo.get_database", return_value=self.database),
        ]

        for started in self._patches:
            started.start()

        self._admin_patch = patch.object(self.client.admin, "command", side_effect=_admin_command)
        self._admin_patch.start()

        initialize_indexes(self.database)
        return self

    def stop(self) -> None:
        if self._admin_patch is not None:
            self._admin_patch.stop()
            self._admin_patch = None
        for p in reversed(self._patches):
            p.stop()
        self._patches.clear()
        self.client = None
        self.database = None

    def repository(self, table: str) -> Repository:
        assert self.database is not None
        return Repository(table, self.database)

    def backdate_draft(self, scope: str, days: int) -> None:
        self.repository("draft_config").collection.update_one(
            {"scope": scope},
            {"$set": {"updated_at": datetime.now(timezone.utc) - timedelta(days=days)}},
        )

    def draft_row_count(self, scope: str) -> int:
        return self.repository("draft_config").count({"scope": scope})

    def __enter__(self) -> MongomockSession:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def start_mongomock() -> MongomockSession:
    """Start mongomock patches and return the session (call ``database.init_db()`` after)."""
    return MongomockSession().start()


def seed_tenant_operations_fixture(database) -> None:
    """Rows for ``test_tenant_operations`` customer/order isolation checks."""
    tenants = Repository("tenants", database)
    for tid in ("tenant-a", "tenant-b"):
        tenants.upsert({"id": tid}, {"id": tid, "display_name": tid})

    orders = Repository("orders", database)
    for row in (
        {
            "order_number": "A-1",
            "wa_id": "shared-wa",
            "items": "[]",
            "total_amount": 50,
            "status": "placed",
            "created_at": "2026-01-01",
            "customer_name": "A Name",
            "customer_mobile": "111",
            "tenant_id": "tenant-a",
        },
        {
            "order_number": "B-1",
            "wa_id": "shared-wa",
            "items": "[]",
            "total_amount": 900,
            "status": "delivered",
            "created_at": "2026-02-01",
            "customer_name": "B Name",
            "customer_mobile": "222",
            "tenant_id": "tenant-b",
        },
        {
            "order_number": "OLD-1",
            "wa_id": "old-wa",
            "items": "[]",
            "total_amount": 12,
            "status": "placed",
            "created_at": "2026-03-01",
            "customer_name": "Legacy",
            "customer_mobile": "333",
            "tenant_id": None,
        },
    ):
        orders.insert(row)

    complaints = Repository("complaints", database)
    complaints.insert(
        {
            "ticket_id": "A-C1",
            "wa_id": "shared-wa",
            "status": "open",
            "created_at": "2026-01-02",
            "tenant_id": "tenant-a",
        }
    )
    complaints.insert(
        {
            "ticket_id": "B-C1",
            "wa_id": "shared-wa",
            "status": "closed",
            "created_at": "2026-02-02",
            "tenant_id": "tenant-b",
        }
    )

    chat = Repository("chat_history", database)
    chat.insert(
        {
            "wa_id": "shared-wa",
            "sender_name": "A Chat Name",
            "message": "A message",
            "response": "",
            "created_at": "2026-01-03",
            "tenant_id": "tenant-a",
        }
    )
    chat.insert(
        {
            "wa_id": "shared-wa",
            "sender_name": "B Chat Name",
            "message": "B message",
            "response": "",
            "created_at": "2026-02-03",
            "tenant_id": "tenant-b",
        }
    )

    Repository("user_states", database).insert(
        {"wa_id": "shared-wa", "updated_at": "2026-02-04", "tenant_id": "tenant-a"}
    )


def seed_campaign_audience(database, tenant_id: str = "acme") -> None:
    """Distributors + chat rows used by ``test_campaigns``."""
    dist = Repository("distributors", database)
    for wa, tier, region, city in (
        ("100012345678901", "Gold", "Gujarat", "Ahmedabad"),
        ("100012345678902", "Platinum", "Gujarat", "Surat"),
        ("100012345678903", "Bronze", "Maharashtra", "Pune"),
    ):
        dist.insert(
            {
                "wa_id": wa,
                "tenant_id": tenant_id,
                "name": wa,
                "tier": tier,
                "region": region,
                "city": city,
            }
        )
    chat = Repository("chat_history", database)
    for wa in ("919876543210", "919876543211"):
        chat.insert(
            {
                "wa_id": wa,
                "tenant_id": tenant_id,
                "message": "hi",
                "response": "hello",
                "route": "faq",
            }
        )