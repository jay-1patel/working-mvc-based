"""Scheduled website-crawl config + crawl-v2 run/staging/image data access.

Extracted from backend/database.py; crawl-v2 tables are additive and do not
change legacy UrlAutoOnboarder publish behaviour.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .core import get_db_context, use_mongodb

logger = logging.getLogger("chiki_webhook")


def _now_ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _parse_ts(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            parsed = datetime.strptime(text.replace("Z", "+0000"), fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        return None


def _crawl_schedule_row(row) -> dict:
    """Map a schedule document/row. Optional fields may be absent on Mongo docs."""
    row = dict(row) if not isinstance(row, dict) else row
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "url": row.get("url"),
        "interval_hours": row.get("interval_hours"),
        "max_pages": row.get("max_pages"),
        "auto_publish": bool(row.get("auto_publish")),
        "is_enabled": bool(row.get("is_enabled")),
        "last_crawled_at": row.get("last_crawled_at"),
        "last_status": row.get("last_status"),
        "last_error": row.get("last_error"),
        "last_pages_found": row.get("last_pages_found"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_crawl_schedule(tenant_id: str) -> dict | None:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("tenant_crawl_schedules").find_one({"tenant_id": tenant_id})
        return _crawl_schedule_row(row) if row else None
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM tenant_crawl_schedules WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
    return _crawl_schedule_row(row) if row else None


def upsert_crawl_schedule(
    tenant_id: str,
    url: str,
    interval_hours: int = 168,
    max_pages: int = None,
    auto_publish: bool = False,
    is_enabled: bool = True,
) -> dict:
    """Upsert schedule. auto_publish is forced off — gated pipeline only.

    max_pages is retained on the row for backward compatibility but is no
    longer applied: the crawler's page-count limit was removed (2026-11-11)
    and scheduled runs ignore any stored value (see crawl_pipeline).
    None is stored as NULL.
    """
    interval_hours = max(1, int(interval_hours or 168))
    max_pages = max(1, int(max_pages)) if max_pages else None
    auto_publish = False  # scheduled crawls never auto-publish
    if use_mongodb():
        from .mongo import Repository
        row = Repository("tenant_crawl_schedules").upsert(
            {"tenant_id": tenant_id},
            {
                "tenant_id": tenant_id,
                "url": url,
                "interval_hours": interval_hours,
                "max_pages": max_pages,
                "auto_publish": 0,
                "is_enabled": 1 if is_enabled else 0,
                "updated_at": _now_ts(),
            },
        )
        return _crawl_schedule_row(row)
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO tenant_crawl_schedules
                   (tenant_id, url, interval_hours, max_pages, auto_publish, is_enabled)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id) DO UPDATE SET
                   url = excluded.url,
                   interval_hours = excluded.interval_hours,
                   max_pages = excluded.max_pages,
                   auto_publish = 0,
                   is_enabled = excluded.is_enabled,
                   updated_at = CURRENT_TIMESTAMP""",
            (tenant_id, url, interval_hours, max_pages, 0, 1 if is_enabled else 0),
        )
        row = conn.execute(
            "SELECT * FROM tenant_crawl_schedules WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
    return _crawl_schedule_row(row)


def delete_crawl_schedule(tenant_id: str) -> bool:
    if use_mongodb():
        from .mongo import Repository
        return Repository("tenant_crawl_schedules").delete_one({"tenant_id": tenant_id}) > 0
    with get_db_context() as conn:
        cur = conn.execute(
            "DELETE FROM tenant_crawl_schedules WHERE tenant_id = ?",
            (tenant_id,),
        )
    return cur.rowcount > 0


def list_due_crawl_schedules() -> list:
    """Enabled schedules whose last crawl is older than their interval (or never crawled)."""
    if use_mongodb():
        from .mongo import Repository
        now = datetime.now(timezone.utc)
        rows = Repository("tenant_crawl_schedules").find_all(
            {"is_enabled": {"$in": [1, True]}},
        )
        due = []
        for r in rows:
            if not bool(r.get("is_enabled")):
                continue
            last = _parse_ts(r.get("last_crawled_at"))
            interval = max(1, int(r.get("interval_hours") or 168))
            if last is None or last <= now - timedelta(hours=interval):
                due.append(r)
        due.sort(
            key=lambda x: _parse_ts(x.get("last_crawled_at"))
            or datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
        return [_crawl_schedule_row(r) for r in due]
    with get_db_context() as conn:
        rows = conn.execute(
            """SELECT * FROM tenant_crawl_schedules
               WHERE is_enabled = 1
                 AND (last_crawled_at IS NULL
                      OR last_crawled_at <= DATETIME('now', '-' || interval_hours || ' hours'))
               ORDER BY COALESCE(last_crawled_at, '1970-01-01') ASC""",
        ).fetchall()
    return [_crawl_schedule_row(r) for r in rows]


def mark_crawl_started(tenant_id: str) -> None:
    """Stamp the run time up-front so a slow crawl is not picked up twice."""
    if use_mongodb():
        from .mongo import Repository
        ts = _now_ts()
        Repository("tenant_crawl_schedules").update(
            {"tenant_id": tenant_id},
            {
                "last_crawled_at": ts,
                "last_status": "running",
                "last_error": None,
                "updated_at": ts,
            },
        )
        return
    with get_db_context() as conn:
        conn.execute(
            """UPDATE tenant_crawl_schedules
               SET last_crawled_at = CURRENT_TIMESTAMP,
                   last_status = 'running',
                   last_error = NULL,
                   updated_at = CURRENT_TIMESTAMP
               WHERE tenant_id = ?""",
            (tenant_id,),
        )


def mark_crawl_finished(
    tenant_id: str,
    status: str,
    error: str = None,
    pages_found: int = None,
) -> None:
    if use_mongodb():
        from .mongo import Repository
        changes = {
            "last_status": status,
            "last_error": error,
            "updated_at": _now_ts(),
        }
        if pages_found is not None:
            changes["last_pages_found"] = int(pages_found)
        Repository("tenant_crawl_schedules").update({"tenant_id": tenant_id}, changes)
        return
    with get_db_context() as conn:
        if pages_found is not None:
            conn.execute(
                """UPDATE tenant_crawl_schedules
                   SET last_status = ?, last_error = ?, last_pages_found = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE tenant_id = ?""",
                (status, error, int(pages_found), tenant_id),
            )
        else:
            conn.execute(
                """UPDATE tenant_crawl_schedules
                   SET last_status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE tenant_id = ?""",
                (status, error, tenant_id),
            )


# ── Crawl v2 runs / pages / staging / images ──────────────────────────────


def _run_row(row) -> dict:
    row = dict(row) if not isinstance(row, dict) else row
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "source_url": row.get("source_url"),
        "trigger": row.get("trigger"),
        "status": row.get("status"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "pages_found": row.get("pages_found") or 0,
        "pages_scraped": row.get("pages_scraped") or 0,
        "error": row.get("error"),
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
    }


def create_crawl_run(
    tenant_id: str,
    source_url: str,
    trigger: str = "manual",
    created_by: str = None,
) -> dict:
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("tenant_crawl_runs")
        inserted = repo.insert({
            "tenant_id": tenant_id,
            "source_url": source_url,
            "trigger": trigger,
            "status": "queued",
            "created_by": created_by,
        })
        row = repo.find_one({"id": inserted["id"]})
        return _run_row(row)
    with get_db_context() as conn:
        cur = conn.execute(
            """INSERT INTO tenant_crawl_runs
                   (tenant_id, source_url, trigger, status, created_by)
               VALUES (?, ?, ?, 'queued', ?)""",
            (tenant_id, source_url, trigger, created_by),
        )
        run_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM tenant_crawl_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _run_row(row)


def get_crawl_run(run_id: int, tenant_id: str = None) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository
        filters = {"id": run_id}
        if tenant_id:
            filters["tenant_id"] = tenant_id
        row = Repository("tenant_crawl_runs").find_one(filters)
        return _run_row(row) if row else None
    with get_db_context() as conn:
        if tenant_id:
            row = conn.execute(
                "SELECT * FROM tenant_crawl_runs WHERE id = ? AND tenant_id = ?",
                (run_id, tenant_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM tenant_crawl_runs WHERE id = ?", (run_id,)
            ).fetchone()
    return _run_row(row) if row else None


def list_crawl_runs(tenant_id: str, limit: int = 20) -> List[dict]:
    cap = max(1, min(int(limit or 20), 100))
    if use_mongodb():
        from .mongo import Repository
        rows = Repository("tenant_crawl_runs").find(
            {"tenant_id": tenant_id},
            sort=[("id", -1)],
            limit=cap,
        )
        return [_run_row(r) for r in rows]
    with get_db_context() as conn:
        rows = conn.execute(
            """SELECT * FROM tenant_crawl_runs
               WHERE tenant_id = ?
               ORDER BY id DESC LIMIT ?""",
            (tenant_id, cap),
        ).fetchall()
    return [_run_row(r) for r in rows]


def get_running_crawl(tenant_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository
        rows = Repository("tenant_crawl_runs").find(
            {"tenant_id": tenant_id, "status": {"$in": ["queued", "running"]}},
            sort=[("id", -1)],
            limit=1,
        )
        return _run_row(rows[0]) if rows else None
    with get_db_context() as conn:
        row = conn.execute(
            """SELECT * FROM tenant_crawl_runs
               WHERE tenant_id = ? AND status IN ('queued', 'running')
               ORDER BY id DESC LIMIT 1""",
            (tenant_id,),
        ).fetchone()
    return _run_row(row) if row else None


def _orphan_stale_seconds() -> float:
    """Age after which a queued/running crawl is treated as orphaned.

    Defaults to the crawl total budget + 10 minutes. Override with
    CRAWL_ORPHAN_SECONDS. Crawls run in-process (FastAPI BackgroundTasks),
    so a server stop leaves rows stuck in queued/running forever without
    this reaper.
    """
    import os

    raw = (os.environ.get("CRAWL_ORPHAN_SECONDS") or "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    try:
        budget = float(os.environ.get("CRAWL_TOTAL_TIMEOUT_SECONDS", "1800"))
    except (TypeError, ValueError):
        budget = 1800.0
    if budget <= 0:
        budget = 1800.0
    return budget + 600.0


def reap_orphaned_crawl_runs(
    *,
    tenant_id: Optional[str] = None,
    force_all: bool = False,
    reason: str = "crawl worker died / server stopped (auto recovery)",
) -> List[dict]:
    """Mark orphaned queued/running crawl runs as failed.

    ``force_all=True`` (startup): every queued/running run is orphaned —
    in-process BackgroundTasks cannot outlive the previous process.

    Otherwise only runs older than ``CRAWL_ORPHAN_SECONDS`` are reaped, so
    a live crawl still in progress is left alone.
    """
    cutoff = None if force_all else (
        datetime.now(timezone.utc) - timedelta(seconds=_orphan_stale_seconds())
    )
    reaped: List[dict] = []

    def _is_stale(row: dict) -> bool:
        if force_all:
            return True
        stamp = _parse_ts(row.get("started_at")) or _parse_ts(row.get("created_at"))
        if stamp is None:
            return True
        return stamp <= cutoff  # type: ignore[operator]

    error_text = (reason or "orphaned crawl")[:500]

    if use_mongodb():
        from .mongo import Repository

        filters: Dict[str, Any] = {"status": {"$in": ["queued", "running"]}}
        if tenant_id:
            filters["tenant_id"] = tenant_id
        repo = Repository("tenant_crawl_runs")
        rows = repo.find(filters, sort=[("id", -1)], limit=500) or []
        touched_tenants: set[str] = set()
        for raw in rows:
            row = _run_row(raw)
            if not row or not _is_stale(raw if isinstance(raw, dict) else row):
                continue
            run_id = row["id"]
            pages = int(row.get("pages_scraped") or 0)
            msg = f"Marked failed: {error_text}"
            if pages:
                msg = f"{msg} after {pages} page(s)"
            update_crawl_run(
                run_id,
                status="failed",
                error=msg[:500],
                mark_finished=True,
            )
            tid = (row.get("tenant_id") or "").strip()
            if tid:
                touched_tenants.add(tid)
            reaped.append(row)
            logger.warning(
                "CRAWL_ORPHAN_REAPED | run=%s tenant=%s pages=%s force=%s",
                run_id, tid or "?", pages, force_all,
            )
        for tid in touched_tenants:
            try:
                schedule = get_crawl_schedule(tid)
                if schedule and schedule.get("last_status") == "running":
                    mark_crawl_finished(tid, "failed", error_text[:500])
            except Exception:
                logger.exception("CRAWL_ORPHAN_SCHEDULE_CLEAR_FAILED | tenant=%s", tid)
        return reaped

    with get_db_context() as conn:
        if tenant_id:
            rows = conn.execute(
                """SELECT * FROM tenant_crawl_runs
                   WHERE tenant_id = ? AND status IN ('queued', 'running')
                   ORDER BY id DESC""",
                (tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM tenant_crawl_runs
                   WHERE status IN ('queued', 'running')
                   ORDER BY id DESC"""
            ).fetchall()
        touched_tenants = set()
        for raw in rows:
            row = _run_row(raw)
            if not row or not _is_stale(dict(raw) if hasattr(raw, "keys") else row):
                continue
            run_id = row["id"]
            pages = int(row.get("pages_scraped") or 0)
            msg = f"Marked failed: {error_text}"
            if pages:
                msg = f"{msg} after {pages} page(s)"
            conn.execute(
                """UPDATE tenant_crawl_runs
                   SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status IN ('queued', 'running')""",
                (msg[:500], run_id),
            )
            tid = (row.get("tenant_id") or "").strip()
            if tid:
                touched_tenants.add(tid)
            reaped.append(row)
            logger.warning(
                "CRAWL_ORPHAN_REAPED | run=%s tenant=%s pages=%s force=%s",
                run_id, tid or "?", pages, force_all,
            )
        for tid in touched_tenants:
            conn.execute(
                """UPDATE tenant_crawl_schedules
                   SET last_status = 'failed', last_error = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE tenant_id = ? AND last_status = 'running'""",
                (error_text[:500], tid),
            )
    return reaped


def update_crawl_run(
    run_id: int,
    *,
    status: str = None,
    pages_found: int = None,
    pages_scraped: int = None,
    error: str = None,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> None:
    if use_mongodb():
        from .mongo import Repository
        changes: Dict[str, Any] = {}
        if status is not None:
            changes["status"] = status
        if pages_found is not None:
            changes["pages_found"] = int(pages_found)
        if pages_scraped is not None:
            changes["pages_scraped"] = int(pages_scraped)
        if error is not None:
            changes["error"] = error
        if mark_started:
            changes["started_at"] = _now_ts()
        if mark_finished:
            changes["finished_at"] = _now_ts()
        if not changes:
            return
        Repository("tenant_crawl_runs").update({"id": run_id}, changes)
        return
    sets = []
    params: list = []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if pages_found is not None:
        sets.append("pages_found = ?")
        params.append(int(pages_found))
    if pages_scraped is not None:
        sets.append("pages_scraped = ?")
        params.append(int(pages_scraped))
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    if mark_started:
        sets.append("started_at = CURRENT_TIMESTAMP")
    if mark_finished:
        sets.append("finished_at = CURRENT_TIMESTAMP")
    if not sets:
        return
    params.append(run_id)
    with get_db_context() as conn:
        conn.execute(
            f"UPDATE tenant_crawl_runs SET {', '.join(sets)} WHERE id = ?",
            params,
        )


def insert_crawl_page(
    run_id: int,
    url: str,
    source: str = "link",
    status: str = None,
    http_status: int = None,
    word_count: int = 0,
    error: str = None,
) -> int:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("tenant_crawl_pages").insert({
            "run_id": run_id,
            "url": url,
            "source": source,
            "status": status,
            "http_status": http_status,
            "word_count": word_count or 0,
            "error": error,
        })
        return row["id"]
    with get_db_context() as conn:
        cur = conn.execute(
            """INSERT INTO tenant_crawl_pages
                   (run_id, url, source, status, http_status, word_count, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (run_id, url, source, status, http_status, word_count or 0, error),
        )
        return cur.lastrowid


def list_crawl_pages(run_id: int) -> List[dict]:
    if use_mongodb():
        from .mongo import Repository
        rows = Repository("tenant_crawl_pages").find(
            {"run_id": run_id},
            sort=[("id", 1)],
            limit=500,
        )
        return [
            {
                "id": r["id"],
                "run_id": r["run_id"],
                "url": r["url"],
                "source": r["source"],
                "status": r["status"],
                "http_status": r["http_status"],
                "word_count": r["word_count"] or 0,
                "error": r["error"],
            }
            for r in rows
        ]
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT * FROM tenant_crawl_pages WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "run_id": r["run_id"],
            "url": r["url"],
            "source": r["source"],
            "status": r["status"],
            "http_status": r["http_status"],
            "word_count": r["word_count"] or 0,
            "error": r["error"],
        }
        for r in rows
    ]


def save_crawl_staged(run_id: int, tenant_id: str, payload: Dict[str, Any]) -> dict:
    payload_json = json.dumps(payload, ensure_ascii=False)
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("tenant_crawl_staged")
        row = repo.upsert(
            {"run_id": run_id},
            {
                "run_id": run_id,
                "tenant_id": tenant_id,
                "payload_json": payload_json,
                "status": "staged",
                "decided_by": None,
                "decided_at": None,
            },
        )
        return _staged_row(row)
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO tenant_crawl_staged (run_id, tenant_id, payload_json, status)
               VALUES (?, ?, ?, 'staged')
               ON CONFLICT(run_id) DO UPDATE SET
                   payload_json = excluded.payload_json,
                   status = 'staged',
                   decided_by = NULL,
                   decided_at = NULL""",
            (run_id, tenant_id, payload_json),
        )
        row = conn.execute(
            "SELECT * FROM tenant_crawl_staged WHERE run_id = ?", (run_id,)
        ).fetchone()
    return _staged_row(row)


def get_crawl_staged(run_id: int, tenant_id: str = None) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository
        filters: Dict[str, Any] = {"run_id": run_id}
        if tenant_id:
            filters["tenant_id"] = tenant_id
        row = Repository("tenant_crawl_staged").find_one(filters)
        return _staged_row(row) if row else None
    with get_db_context() as conn:
        if tenant_id:
            row = conn.execute(
                "SELECT * FROM tenant_crawl_staged WHERE run_id = ? AND tenant_id = ?",
                (run_id, tenant_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM tenant_crawl_staged WHERE run_id = ?", (run_id,)
            ).fetchone()
    return _staged_row(row) if row else None


def decide_crawl_staged(
    run_id: int,
    tenant_id: str,
    decision: str,
    decided_by: str = None,
) -> Optional[dict]:
    """Mark staged row published/rejected. Returns None if missing; raises ValueError if already decided."""
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("tenant_crawl_staged")
        row = repo.find_one({"run_id": run_id, "tenant_id": tenant_id})
        if not row:
            return None
        current = row["status"]
        if current != "staged":
            raise ValueError(f"already_{current}")
        ts = _now_ts()
        repo.update(
            {"run_id": run_id, "tenant_id": tenant_id},
            {"status": decision, "decided_by": decided_by, "decided_at": ts},
        )
        row = repo.find_one({"run_id": run_id})
        return _staged_row(row)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM tenant_crawl_staged WHERE run_id = ? AND tenant_id = ?",
            (run_id, tenant_id),
        ).fetchone()
        if not row:
            return None
        current = row["status"]
        if current != "staged":
            raise ValueError(f"already_{current}")
        conn.execute(
            """UPDATE tenant_crawl_staged
               SET status = ?, decided_by = ?, decided_at = CURRENT_TIMESTAMP
               WHERE run_id = ? AND tenant_id = ?""",
            (decision, decided_by, run_id, tenant_id),
        )
        row = conn.execute(
            "SELECT * FROM tenant_crawl_staged WHERE run_id = ?", (run_id,)
        ).fetchone()
    return _staged_row(row)


def _staged_row(row) -> dict:
    payload = {}
    try:
        raw = row["payload_json"]
        if isinstance(raw, dict):
            payload = raw
        else:
            payload = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "tenant_id": row["tenant_id"],
        "payload": payload,
        "status": row["status"],
        "decided_by": row["decided_by"],
        "decided_at": row["decided_at"],
        "created_at": row["created_at"],
    }


def insert_crawl_image(row: Dict[str, Any]) -> int:
    values = (
        row.get("run_id"),
        row.get("tenant_id"),
        row.get("source_url"),
        row.get("local_path"),
        row.get("served_url"),
        row.get("content_type"),
        row.get("sha256"),
        row.get("byte_size"),
        row.get("width"),
        row.get("height"),
        row.get("alt_text"),
        row.get("source_page_url"),
        row.get("offering_name"),
        row.get("kind") or "image",
        1 if row.get("is_duplicate") else 0,
        row.get("duplicate_of"),
        1 if row.get("skipped") else 0,
        row.get("skip_reason"),
    )
    if use_mongodb():
        from .mongo import Repository
        inserted = Repository("tenant_crawl_images").insert({
            "run_id": values[0],
            "tenant_id": values[1],
            "source_url": values[2],
            "local_path": values[3],
            "served_url": values[4],
            "content_type": values[5],
            "sha256": values[6],
            "byte_size": values[7],
            "width": values[8],
            "height": values[9],
            "alt_text": values[10],
            "source_page_url": values[11],
            "offering_name": values[12],
            "kind": values[13],
            "is_duplicate": values[14],
            "duplicate_of": values[15],
            "skipped": values[16],
            "skip_reason": values[17],
        })
        return inserted["id"]
    with get_db_context() as conn:
        cur = conn.execute(
            """INSERT INTO tenant_crawl_images
                   (run_id, tenant_id, source_url, local_path, served_url, content_type,
                    sha256, byte_size, width, height, alt_text, source_page_url,
                    offering_name, kind, is_duplicate, duplicate_of, skipped, skip_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
        return cur.lastrowid


def list_crawl_images(run_id: int, tenant_id: str = None) -> List[dict]:
    if use_mongodb():
        from .mongo import Repository
        filters: Dict[str, Any] = {"run_id": run_id}
        if tenant_id:
            filters["tenant_id"] = tenant_id
        rows = Repository("tenant_crawl_images").find(
            filters,
            sort=[("id", 1)],
            limit=500,
        )
        return [_image_row(r) for r in rows]
    with get_db_context() as conn:
        if tenant_id:
            rows = conn.execute(
                "SELECT * FROM tenant_crawl_images WHERE run_id = ? AND tenant_id = ? ORDER BY id ASC",
                (run_id, tenant_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tenant_crawl_images WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
    return [_image_row(r) for r in rows]


def _image_row(r) -> dict:
    return {
        "id": r["id"],
        "run_id": r["run_id"],
        "tenant_id": r["tenant_id"],
        "source_url": r["source_url"],
        "local_path": r["local_path"],
        "served_url": r["served_url"],
        "content_type": r["content_type"],
        "sha256": r["sha256"],
        "byte_size": r["byte_size"],
        "width": r["width"],
        "height": r["height"],
        "alt_text": r["alt_text"],
        "source_page_url": r["source_page_url"],
        "offering_name": r["offering_name"],
        "kind": r["kind"],
        "is_duplicate": bool(r["is_duplicate"]),
        "duplicate_of": r["duplicate_of"],
        "skipped": bool(r["skipped"]),
        "skip_reason": r["skip_reason"],
        "created_at": r["created_at"],
    }


def find_crawl_image_by_sha(run_id: int, sha256: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("tenant_crawl_images").find_one({
            "run_id": run_id,
            "sha256": sha256,
            "skipped": 0,
            "is_duplicate": 0,
        })
        if not row:
            return None
        return {
            "id": row["id"],
            "local_path": row["local_path"],
            "served_url": row["served_url"],
            "source_url": row["source_url"],
        }
    with get_db_context() as conn:
        row = conn.execute(
            """SELECT * FROM tenant_crawl_images
               WHERE run_id = ? AND sha256 = ? AND skipped = 0 AND is_duplicate = 0
               ORDER BY id ASC LIMIT 1""",
            (run_id, sha256),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "local_path": row["local_path"],
        "served_url": row["served_url"],
        "source_url": row["source_url"],
    }


def find_crawl_image_by_source_url(run_id: int, source_url: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("tenant_crawl_images").find_one({
            "run_id": run_id,
            "source_url": source_url,
        })
        if not row:
            return None
        return {
            "id": row["id"],
            "local_path": row["local_path"],
            "served_url": row["served_url"],
            "sha256": row["sha256"],
            "skipped": bool(row["skipped"]),
            "is_duplicate": bool(row["is_duplicate"]),
        }
    with get_db_context() as conn:
        row = conn.execute(
            """SELECT * FROM tenant_crawl_images
               WHERE run_id = ? AND source_url = ?
               ORDER BY id ASC LIMIT 1""",
            (run_id, source_url),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "local_path": row["local_path"],
        "served_url": row["served_url"],
        "sha256": row["sha256"],
        "skipped": bool(row["skipped"]),
        "is_duplicate": bool(row["is_duplicate"]),
    }
