#!/usr/bin/env python3
"""Legacy one-shot SQLite migration — obsolete after Mongo-only cutover.

B2C cart/checkout collections are defined in ``db/mongo_schema.json``.
Run ``scripts/bootstrap_mongodb.py`` instead of this script.
"""

raise SystemExit(
    "Obsolete: this project uses MongoDB only. "
    "Use scripts/bootstrap_mongodb.py / initialize_indexes."
)