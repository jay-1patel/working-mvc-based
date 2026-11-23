"""Copy every SQLite table into its MongoDB collection (idempotent clear-and-reload).

Usage (from repo root, with MONGODB_URI pointing at rs0):
  python scripts/migrate_sqlite_to_mongo.py [--sqlite PATH] [--sample N]

Safe to re-run: each registered collection is dropped-and-reloaded (or emptied)
before insert. Prints a per-table SQLite vs Mongo count report.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def migrate(sqlite_path: Path, sample: int = 3) -> int:
    load_dotenv(ROOT / "routing" / ".env")
    os.environ.setdefault("DATABASE_BACKEND", "mongodb")

    from backend.db.mongo import (
        REGISTRY,
        Repository,
        encode_row,
        get_database,
        initialize_indexes,
        public_row,
        require_replica_set,
    )

    if not sqlite_path.exists():
        print(json.dumps({"ok": False, "reason": f"SQLite file missing: {sqlite_path}"}))
        return 1

    database = get_database()
    require_replica_set(database)
    initialize_indexes(database)

    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_tables = {
        row[0]
        for row in sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }

    report = []
    mismatches = 0

    for table in sorted(REGISTRY["tables"]):
        if table not in sqlite_tables:
            mongo_count = database[table].count_documents({})
            report.append({
                "table": table,
                "sqlite": 0,
                "mongo": mongo_count,
                "status": "SKIP_MISSING_IN_SQLITE",
            })
            continue

        rows = [_row_to_dict(r) for r in sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()]
        sqlite_count = len(rows)

        # Idempotent clear-and-reload: drop the collection so unique indexes
        # cannot collide with a half-written previous run, then recreate indexes.
        database.drop_collection(table)
        from backend.db.mongo import initialize_indexes as _init_indexes  # noqa: F401 — indexes rebuilt below
        # Recreate only this collection's indexes (initialize_indexes is global; mirror one table).
        definition = REGISTRY["tables"][table]
        if table not in database.list_collection_names():
            database.create_collection(table)
        collection = database[table]
        seen = set()
        for index in definition["indexes"]:
            signature = json.dumps(
                {"keys": index["keys"], "options": {
                    key: value for key, value in index["options"].items() if key != "name"
                }},
                sort_keys=True,
            )
            if signature in seen:
                continue
            seen.add(signature)
            collection.create_index([tuple(key) for key in index["keys"]], **index["options"])
        if any(c["name"] == "tenant_id" for c in definition["columns"]):
            try:
                collection.create_index([("tenant_id", 1)], name="mongo_tenant_lookup")
            except Exception:
                pass

        # Reset the integer id counter so next_id stays consistent with imported ids.
        max_id = 0
        for row in rows:
            if isinstance(row.get("id"), int):
                max_id = max(max_id, row["id"])
        if max_id:
            database["_counters"].update_one(
                {"_id": table},
                {"$set": {"seq": max_id}},
                upsert=True,
            )
        else:
            database["_counters"].delete_one({"_id": table})

        repo = Repository(table, database)
        sample_ok = True
        checked = 0
        for row in rows:
            document = encode_row(table, row)
            # Preserve explicit primary key values from SQLite.
            database[table].insert_one(document)
            if sample > 0 and checked < sample:
                pk = REGISTRY["tables"][table]["primary_key"]
                filters = {key: document.get(key) for key in pk if key in document}
                if filters:
                    found = repo.find_one(filters)
                    expected = public_row(table, document)
                    for key in ("id", "tenant_id"):
                        if key in expected and found is not None and found.get(key) != expected.get(key):
                            sample_ok = False
                            break
                    checked += 1

        mongo_count = database[table].count_documents({})
        status = "OK" if mongo_count == sqlite_count and sample_ok else "MISMATCH"
        if status != "OK":
            mismatches += 1
        report.append({
            "table": table,
            "sqlite": sqlite_count,
            "mongo": mongo_count,
            "status": status,
            "sample_ok": sample_ok,
        })

    sqlite_conn.close()

    print("\n=== SQLite → Mongo migration report ===")
    print(f"{'table':40} {'sqlite':>8} {'mongo':>8}  status")
    for item in report:
        print(f"{item['table']:40} {item['sqlite']:8} {item['mongo']:8}  {item['status']}")
    print(f"\nTables: {len(report)} | mismatches: {mismatches}")
    print(json.dumps({"ok": mismatches == 0, "mismatches": mismatches, "tables": len(report)}))
    return 0 if mismatches == 0 else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite",
        default=str(ROOT / "faq.db"),
        help="Path to the source SQLite database (default: ./faq.db)",
    )
    parser.add_argument("--sample", type=int, default=3, help="Sample rows to spot-check per table")
    args = parser.parse_args()
    raise SystemExit(migrate(Path(args.sqlite), sample=args.sample))


if __name__ == "__main__":
    main()
