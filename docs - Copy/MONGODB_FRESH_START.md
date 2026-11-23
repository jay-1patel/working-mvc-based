# Fresh MongoDB setup — conversion in progress

The user superseded the data-migration plan with a fresh database. No old users,
businesses, messages, documents, or authentication records are to be copied.
The original database file is retained untouched as an offline backup.

## Implemented

- Native PyMongo connection pooling, atomic ID counters, JSON/date/binary codecs,
  native schema defaults, and declarative MongoDB indexes.
- All 76 empty application collections and their indexes created in `tmpdbtest`.
- A native schema file without relational DDL. Removed the earlier registry
  generator, import/verification/export scripts, and migration-specific tests.
- Error reporting now persists and queries MongoDB directly. Its unit tests use
  isolated mocked MongoDB collections, never the actual user's database.
- Bootstrap and diagnostics scripts do not import or open the old database.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap_mongodb.py
.\.venv\Scripts\python.exe scripts/mongodb_preflight.py
```

Bootstrap is idempotent. It refuses to adopt unrelated collections or erase
existing records. It creates no administrator account. Connection credentials
remain only in the ignored environment file and are never printed by diagnostics.

## Remaining work — do not claim Mongo-only runtime yet

The original application still has SQL-backed domain modules, route queries,
authentication queries, FAQ/KB retrieval, and background jobs. These must be
converted to native repositories before switching the entire application.
Creating collections is not the same as completing that conversion.

Do not change the active backend setting until all these callers are converted
and integration tests pass. The existing SQL facade rejects MongoDB mode rather
than silently falling back. First-run administrator setup must ultimately write
to MongoDB after authentication is converted; existing accounts are not imported.

The server currently runs standalone. Basic document operations and collection
creation work, but transaction-dependent publishing/approval workflows still
need replica set `rs0` before their production cutover. A single-member replica
set adds transactions but not redundancy. Database administration must preserve
authentication, private bind addresses, storage paths, and firewall protection.
