"""Draft + published config store (generic scopes) data access — extracted from backend/database.py."""
import json
from datetime import datetime, timedelta, timezone

from .core import logger, get_db_context, use_mongodb, _loads_json


def _as_snapshot(value):
    if isinstance(value, dict):
        return value
    return _loads_json(value)


def get_published_config(scope: str, default=None):
    """Return the published JSON snapshot for a scope, or default."""
    if use_mongodb():
        from .mongo import Repository
        row = Repository("published_config").find_one({"scope": scope})
        if not row or row.get("snapshot_json") in (None, ""):
            return default if default is not None else None
        return _as_snapshot(row.get("snapshot_json"))
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT snapshot_json FROM published_config WHERE scope = ?", (scope,)
        ).fetchone()
    if not row or not row["snapshot_json"]:
        return default if default is not None else None
    return _loads_json(row["snapshot_json"])


def get_draft_config(scope: str, default=None, max_age_days=None):
    """Return the draft JSON snapshot for a scope, or default.

    With ``max_age_days`` the draft also acts as a working-copy lease: a
    row whose last save is older than the limit is deleted instead of
    returned, so an unpublishable draft cannot linger forever. ``updated_at``
    is refreshed on every save, so publishing or re-saving always extends it.
    """
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("draft_config")
        row = repo.find_one({"scope": scope})
        if row and max_age_days is not None:
            updated = row.get("updated_at")
            age_days = 0.0
            if updated:
                if isinstance(updated, str):
                    try:
                        updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    except ValueError:
                        updated = None
                if isinstance(updated, datetime):
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds() / 86400.0
            if age_days > float(max_age_days):
                repo.delete_one({"scope": scope})
                row = None
        if not row or row.get("snapshot_json") in (None, ""):
            return default if default is not None else None
        return _as_snapshot(row.get("snapshot_json"))
    with get_db_context() as conn:
        if max_age_days is None:
            row = conn.execute(
                "SELECT snapshot_json FROM draft_config WHERE scope = ?", (scope,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT snapshot_json, COALESCE("
                "    julianday(CURRENT_TIMESTAMP) - julianday(updated_at), 0) AS age_days"
                " FROM draft_config WHERE scope = ?",
                (scope,),
            ).fetchone()
            if row and float(row["age_days"] or 0) > float(max_age_days):
                # Stale working copy: discard it rather than resurrect it.
                conn.execute("DELETE FROM draft_config WHERE scope = ?", (scope,))
                row = None
    if not row or not row["snapshot_json"]:
        return default if default is not None else None
    return _loads_json(row["snapshot_json"])


def save_draft_config(scope: str, snapshot: dict, updated_by: str = "", conn=None) -> bool:
    """Save a draft snapshot for a scope. Does not affect the live bot."""
    if use_mongodb() and conn is None:
        from .mongo import Repository
        Repository("draft_config").upsert(
            {"scope": scope},
            {
                "scope": scope,
                "snapshot_json": snapshot,
                "updated_by": updated_by,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        return True
    payload = json.dumps(snapshot)

    def _save(connection):
        connection.execute(
            """INSERT INTO draft_config (scope, snapshot_json, updated_by, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(scope) DO UPDATE SET
                   snapshot_json = excluded.snapshot_json,
                   updated_by = excluded.updated_by,
                   updated_at = CURRENT_TIMESTAMP""",
            (scope, payload, updated_by),
        )

    if conn is None:
        with get_db_context() as own_conn:
            _save(own_conn)
    else:
        _save(conn)
    return True


def publish_config(scope: str, published_by: str = "", conn=None) -> bool:
    """Copy the current draft to published and append to history.

    If no draft exists, the published config is left unchanged.
    """
    if use_mongodb() and conn is None:
        from .mongo import Repository
        draft = Repository("draft_config").find_one({"scope": scope})
        if not draft:
            return False
        snapshot = draft.get("snapshot_json")
        now = datetime.now(timezone.utc)
        Repository("published_config").upsert(
            {"scope": scope},
            {
                "scope": scope,
                "snapshot_json": snapshot if isinstance(snapshot, dict) else _loads_json(snapshot, {}),
                "published_by": published_by,
                "published_at": now,
            },
        )
        Repository("publish_history").insert({
            "scope": scope,
            "snapshot_json": snapshot if isinstance(snapshot, dict) else _loads_json(snapshot, {}),
            "published_by": published_by,
            "published_at": now,
        })
        return True

    def _publish(connection):
        draft = connection.execute(
            "SELECT snapshot_json FROM draft_config WHERE scope = ?", (scope,)
        ).fetchone()
        if not draft:
            return False
        snapshot_json = draft["snapshot_json"]
        connection.execute(
            """INSERT INTO published_config (scope, snapshot_json, published_by, published_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(scope) DO UPDATE SET
                   snapshot_json = excluded.snapshot_json,
                   published_by = excluded.published_by,
                   published_at = excluded.published_at""",
            (scope, snapshot_json, published_by),
        )
        connection.execute(
            "INSERT INTO publish_history (scope, snapshot_json, published_by, published_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (scope, snapshot_json, published_by),
        )
        return True

    if conn is None:
        with get_db_context() as own_conn:
            return _publish(own_conn)
    return _publish(conn)


def get_publish_history(scope: str, limit: int = 20) -> list:
    """Return recent publish events for a scope, newest first."""
    if use_mongodb():
        from .mongo import Repository
        rows = Repository("publish_history").find(
            {"scope": scope},
            sort=[("published_at", -1)],
            limit=limit,
        )
        return [
            {
                "id": r.get("id"),
                "scope": r.get("scope"),
                "snapshot": _as_snapshot(r.get("snapshot_json")),
                "published_by": r.get("published_by"),
                "published_at": r.get("published_at"),
            }
            for r in rows
        ]
    with get_db_context() as conn:
        rows = conn.execute(
            """SELECT id, scope, snapshot_json, published_by, published_at
                 FROM publish_history
                WHERE scope = ?
                ORDER BY published_at DESC
                LIMIT ?""",
            (scope, limit),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "scope": r["scope"],
            "snapshot": _loads_json(r["snapshot_json"]),
            "published_by": r["published_by"],
            "published_at": r["published_at"],
        }
        for r in rows
    ]
