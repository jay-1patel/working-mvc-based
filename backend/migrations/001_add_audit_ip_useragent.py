#!/usr/bin/env python3
"""Legacy one-shot SQLite migration — obsolete after Mongo-only cutover.

The ``admin_audit_events`` collection is defined in ``db/mongo_schema.json``
(with ``ip_address`` / ``user_agent``). Run ``scripts/bootstrap_mongodb.py``
instead of this script.
"""

raise SystemExit(
    "Obsolete: this project uses MongoDB only. "
    "Use scripts/bootstrap_mongodb.py / initialize_indexes."
)
