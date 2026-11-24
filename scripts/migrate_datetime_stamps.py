"""Rewrite BSON Date fields to ``DD-MM-YYYY HH:mm`` strings across Mongo collections.

Usage (from repo root, with MONGODB_URI set):

    python scripts/migrate_datetime_stamps.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.db.mongo import REGISTRY, get_database
from backend.db.timestamps import to_stamp


def migrate(database=None) -> dict:
    database = get_database() if database is None else database
    report: dict[str, int] = {}
    for table, definition in REGISTRY["tables"].items():
        datetime_cols = [c["name"] for c in definition["columns"] if c.get("kind") == "datetime"]
        if not datetime_cols:
            continue
        collection = database[table]
        changed = 0
        for doc in collection.find({}):
            patch = {}
            for key in datetime_cols:
                if key not in doc or doc[key] is None or doc[key] == "":
                    continue
                stamped = to_stamp(doc[key])
                if stamped is not None and stamped != doc[key]:
                    patch[key] = stamped
            if patch:
                collection.update_one({"_id": doc["_id"]}, {"$set": patch})
                changed += 1
        if changed:
            report[table] = changed
    return report


if __name__ == "__main__":
    if not os.environ.get("MONGODB_URI", "").strip():
        raise SystemExit("MONGODB_URI is required")
    result = migrate()
    if not result:
        print("No documents needed conversion.")
    else:
        for table, count in sorted(result.items()):
            print(f"{table}: {count} document(s) converted")
