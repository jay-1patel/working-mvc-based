"""User conversation state and human-handover flags data access — extracted from backend/database.py."""
import json
from datetime import datetime, timezone
from typing import Optional

from .core import (
    logger, get_db_context, use_mongodb,
    _current_tenant, get_request_tenant, _loads_json
)


def _resolve_tenant_id(wa_id: str, tenant_id: Optional[str] = None) -> str:
    tid = (tenant_id or get_request_tenant() or _current_tenant.get() or "").strip()
    if tid:
        return tid
    try:
        if use_mongodb():
            from .mongo import Repository
            rows = Repository("user_states").find(
                {"wa_id": wa_id, "tenant_id": {"$nin": [None, ""]}},
                sort=[("updated_at", -1)],
                limit=1,
            )
            if rows and rows[0].get("tenant_id"):
                return str(rows[0]["tenant_id"])
        else:
            with get_db_context() as conn:
                row = conn.execute(
                    "SELECT tenant_id FROM user_states WHERE wa_id = ? "
                    "AND tenant_id IS NOT NULL AND TRIM(tenant_id) != '' "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (wa_id,),
                ).fetchone()
                if row and row["tenant_id"]:
                    return str(row["tenant_id"])
    except Exception:
        # deliberate: resolver chain — fall through to the next source.
        logger.debug("STATE_TENANT_RESOLVE_STEP_SKIPPED | source=user_states wa=%s", wa_id, exc_info=True)
    try:
        from shared.tenancy.resolver import resolve_default_tenant
        return resolve_default_tenant()
    except Exception:
        import os
        return os.environ.get("DEFAULT_TENANT_ID", "default")


def get_user_state(wa_id: str, tenant_id: Optional[str] = None) -> dict:
    tid = _resolve_tenant_id(wa_id, tenant_id)
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("user_states")
        row = repo.find_one({"tenant_id": tid, "wa_id": wa_id})
        if row is None:
            row = repo.find_one({"wa_id": wa_id})
        if row:
            result = dict(row)
            ctx = result.get("context_json")
            if isinstance(ctx, dict):
                result["context_json"] = ctx
            else:
                result["context_json"] = _loads_json(ctx, {})
            return result
        return {
            "wa_id": wa_id,
            "tenant_id": tid,
            "state": "MAIN_MENU",
            "context_json": {},
            "lang": "en",
        }
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM user_states WHERE tenant_id = ? AND wa_id = ?",
            (tid, wa_id),
        ).fetchone()
        if row is None:
            # Legacy fallback: wa_id-only row before composite migration completed
            row = conn.execute(
                "SELECT * FROM user_states WHERE wa_id = ? LIMIT 1",
                (wa_id,),
            ).fetchone()
    if row:
        result = dict(row)
        try:
            result["context_json"] = json.loads(result.get("context_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            result["context_json"] = {}
        return result
    return {
        "wa_id": wa_id,
        "tenant_id": tid,
        "state": "MAIN_MENU",
        "context_json": {},
        "lang": "en",
    }


def set_user_state(
    wa_id: str,
    state: str,
    context: dict = None,
    lang: str = None,
    tenant_id: Optional[str] = None,
) -> bool:
    tid = _resolve_tenant_id(wa_id, tenant_id)
    if use_mongodb():
        from .mongo import Repository
        payload = {
            "tenant_id": tid,
            "wa_id": wa_id,
            "state": state,
            "context_json": context or {},
            "updated_at": datetime.now(timezone.utc),
        }
        if lang:
            payload["lang"] = lang
        Repository("user_states").upsert({"tenant_id": tid, "wa_id": wa_id}, payload)
        return True
    with get_db_context() as conn:
        context_json = json.dumps(context or {})
        if lang:
            conn.execute(
                """INSERT INTO user_states (tenant_id, wa_id, state, context_json, lang)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
                     state = excluded.state,
                     context_json = excluded.context_json,
                     lang = excluded.lang,
                     updated_at = CURRENT_TIMESTAMP""",
                (tid, wa_id, state, context_json, lang),
            )
        else:
            conn.execute(
                """INSERT INTO user_states (tenant_id, wa_id, state, context_json)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
                     state = excluded.state,
                     context_json = excluded.context_json,
                     updated_at = CURRENT_TIMESTAMP""",
                (tid, wa_id, state, context_json),
            )
    return True


def update_user_context(wa_id: str, context: dict, tenant_id: Optional[str] = None) -> bool:
    current = get_user_state(wa_id, tenant_id=tenant_id)
    merged = {**current.get("context_json", {}), **context}
    return set_user_state(
        wa_id,
        current.get("state", "MAIN_MENU"),
        merged,
        tenant_id=tenant_id or current.get("tenant_id"),
    )


def clear_user_context(wa_id: str, tenant_id: Optional[str] = None) -> bool:
    return set_user_state(wa_id, "MAIN_MENU", {}, tenant_id=tenant_id)


def _clear_handover_resolved_mongo(repo, filt: dict, now: datetime) -> int:
    """Clear ``handover_resolved_at`` on Mongo.

    ``encode_row`` drops ``None`` values, so ``$set: {handover_resolved_at: null}``
    never writes. Use ``$unset`` instead. Also avoid ``$ne`` filters — this
    Mongo layer only reliably supports equality matches.
    """
    from .mongo import encode_row

    result = repo.collection.update_many(
        filt,
        {
            "$set": encode_row("user_states", {"updated_at": now}),
            "$unset": {"handover_resolved_at": ""},
        },
    )
    return int(getattr(result, "modified_count", 0) or 0)


def set_human_handover(wa_id: str, active: bool, tenant_id: Optional[str] = None) -> bool:
    """Set or clear the human-handover state for a conversation.

    When ``active`` is True the conversation enters the live human inbox and any
    previous "resolved" marker is cleared. When False the human session is
    terminated, control returns to the bot, and ``handover_resolved_at`` is
    stamped so the live inbox stops showing the conversation.
    """
    tid = _resolve_tenant_id(wa_id, tenant_id)
    try:
        if use_mongodb():
            from .mongo import Repository
            now = datetime.now(timezone.utc)
            repo = Repository("user_states")
            payload = {
                "tenant_id": tid,
                "wa_id": wa_id,
                "human_handover": 1 if active else 0,
                "updated_at": now,
            }
            if not active:
                payload["handover_resolved_at"] = now
            repo.upsert({"tenant_id": tid, "wa_id": wa_id}, payload)
            if active:
                _clear_handover_resolved_mongo(
                    repo, {"tenant_id": tid, "wa_id": wa_id}, now
                )
            return True
        with get_db_context() as conn:
            if active:
                conn.execute(
                    """
                    INSERT INTO user_states (tenant_id, wa_id, human_handover, updated_at, handover_resolved_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP, NULL)
                    ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
                        human_handover = 1,
                        updated_at = CURRENT_TIMESTAMP,
                        handover_resolved_at = NULL
                    """,
                    (tid, wa_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_states (tenant_id, wa_id, human_handover, updated_at, handover_resolved_at)
                    VALUES (?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
                        human_handover = 0,
                        updated_at = CURRENT_TIMESTAMP,
                        handover_resolved_at = CURRENT_TIMESTAMP
                    """,
                    (tid, wa_id),
                )
        return True
    except Exception as e:
        logger.error(f"set_human_handover failed for {wa_id}: {e}")
        return False


def touch_handover_activity(wa_id: str, tenant_id: Optional[str] = None) -> None:
    """Refresh user_states.updated_at while human_handover is active."""
    tid = _resolve_tenant_id(wa_id, tenant_id)
    try:
        if use_mongodb():
            from .mongo import Repository
            now = datetime.now(timezone.utc)
            repo = Repository("user_states")
            row = repo.find_one({"tenant_id": tid, "wa_id": wa_id, "human_handover": 1})
            if row:
                repo.update({"id": row["id"]}, {"updated_at": now})
            return
        with get_db_context() as conn:
            conn.execute(
                """
                UPDATE user_states
                SET updated_at = CURRENT_TIMESTAMP
                WHERE wa_id = ? AND human_handover = 1 AND tenant_id = ?
                """,
                (wa_id, tid),
            )
    except Exception as e:
        logger.warning("touch_handover_activity failed for %s: %s", wa_id, e)


def reopen_conversation_on_inbound(wa_id: str, tenant_id: Optional[str] = None) -> bool:
    """Clear a stale ``handover_resolved_at`` so a new inbound message puts the
    conversation back in the live inbox.
    """
    tid = _resolve_tenant_id(wa_id, tenant_id)
    try:
        if use_mongodb():
            from .mongo import Repository
            repo = Repository("user_states")
            now = datetime.now(timezone.utc)
            # Equality-only filters: find rows for this wa_id, then unset.
            cleared = 0
            seen = set()
            rows = list(repo.find_all({"wa_id": wa_id}) or [])
            if tid:
                scoped = repo.find_one({"tenant_id": tid, "wa_id": wa_id})
                if scoped:
                    rows.append(scoped)
            for row in rows:
                if not row or not row.get("handover_resolved_at"):
                    continue
                key = (str(row.get("tenant_id") or ""), str(row.get("wa_id") or ""), str(row.get("id") or ""))
                if key in seen:
                    continue
                seen.add(key)
                if row.get("id") is not None:
                    filt = {"id": row["id"]}
                else:
                    filt = {"tenant_id": row.get("tenant_id"), "wa_id": wa_id}
                cleared += _clear_handover_resolved_mongo(repo, filt, now)
            if cleared:
                logger.info(
                    "INBOX_REOPENED | wa=%s | tenant=%s | cleared=%s",
                    wa_id, tid, cleared,
                )
            return True
        with get_db_context() as conn:
            conn.execute(
                "UPDATE user_states SET handover_resolved_at = NULL, updated_at = CURRENT_TIMESTAMP "
                "WHERE tenant_id = ? AND wa_id = ? AND handover_resolved_at IS NOT NULL",
                (tid, wa_id),
            )
            # Also clear any legacy wa_id-only rows
            conn.execute(
                "UPDATE user_states SET handover_resolved_at = NULL, updated_at = CURRENT_TIMESTAMP "
                "WHERE wa_id = ? AND handover_resolved_at IS NOT NULL",
                (wa_id,),
            )
        return True
    except Exception as e:
        logger.error(f"reopen_conversation_on_inbound failed for {wa_id}: {e}")
        return False
