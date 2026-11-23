"""Callback booking persistence — dual SQLite / Mongo."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from .core import get_db_context, use_mongodb

logger = logging.getLogger("callbacks_ops")


def ensure_callback_tables(conn=None) -> None:
    if use_mongodb():
        return
    if conn is None:
        with get_db_context() as conn:
            _ensure_sqlite_callback_tables(conn)
        return
    _ensure_sqlite_callback_tables(conn)


def _ensure_sqlite_callback_tables(conn) -> None:
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS callbacks (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                wa_id TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                scheduled_start_time TEXT,
                scheduled_end_time TEXT,
                meet_link TEXT,
                calendar_event_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_callbacks_tenant ON callbacks(tenant_id, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_callbacks_wa_id ON callbacks(wa_id, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_callbacks_status ON callbacks(status, created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_callbacks_scheduled ON callbacks(scheduled_start_time)"
    )
    # Additive compatibility migration for callback reliability metadata.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(callbacks)").fetchall()}
    for name, sql_type in (
        ("idempotency_key", "TEXT"),
        ("consent_status", "TEXT"),
        ("consent_at", "TIMESTAMP"),
        ("source_message_id", "TEXT"),
        ("integration_status", "TEXT"),
        ("integration_error", "TEXT"),
        ("tenant_timezone", "TEXT"),
    ):
        if name not in existing_columns:
            conn.execute(f"ALTER TABLE callbacks ADD COLUMN {name} {sql_type}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_callbacks_idempotency ON callbacks(tenant_id, idempotency_key)"
    )
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS callback_summaries (
                id TEXT PRIMARY KEY,
                callback_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                meeting_notes TEXT,
                outcome TEXT,
                follow_up_required BOOLEAN DEFAULT FALSE,
                follow_up_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    )
    conn.execute(
        """
            CREATE TABLE IF NOT EXISTS agent_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                is_available BOOLEAN DEFAULT TRUE,
                UNIQUE(tenant_id, agent_id, date, start_time, end_time)
            )
        """
    )


def save_agent_availability(
    *,
    tenant_id: str,
    agent_id: str,
    agent_name: str,
    date: str,
    start_time: str,
    end_time: str,
    is_available: bool,
) -> None:
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("agent_availability")
        existing = repo.find_one({
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
        })
        payload = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "is_available": bool(is_available),
        }
        if existing:
            repo.update({"id": existing["id"]}, payload)
        else:
            repo.insert(payload)
        return

    with get_db_context() as conn:
        ensure_callback_tables(conn)
        conn.execute(
            """INSERT INTO agent_availability
               (tenant_id, agent_id, agent_name, date, start_time, end_time, is_available)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, agent_id, date, start_time, end_time) DO UPDATE SET
                 is_available = excluded.is_available,
                 agent_name = excluded.agent_name""",
            (tenant_id, agent_id, agent_name, date, start_time, end_time, 1 if is_available else 0),
        )


def list_agent_availability(tenant_id: str, agent_id: str, date: str) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("agent_availability").find(
            {"tenant_id": tenant_id, "agent_id": agent_id, "date": date},
            sort=[("start_time", 1)],
        )
        return [
            {
                "id": r.get("id"),
                "agent_id": r.get("agent_id"),
                "agent_name": r.get("agent_name"),
                "date": r.get("date"),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "is_available": bool(r.get("is_available")),
            }
            for r in rows
        ]

    with get_db_context() as conn:
        ensure_callback_tables(conn)
        rows = conn.execute(
            """SELECT * FROM agent_availability
               WHERE tenant_id = ? AND agent_id = ? AND date = ?
               ORDER BY start_time ASC""",
            (tenant_id, agent_id, date),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "agent_id": row["agent_id"],
                "agent_name": row["agent_name"],
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "is_available": bool(row["is_available"]),
            }
            for row in rows
        ]


def save_callback_summary(summary_id: str, payload: dict) -> None:
    if use_mongodb():
        from .mongo import Repository

        Repository("callback_summaries").upsert({"id": summary_id}, payload)
        return
    with get_db_context() as conn:
        ensure_callback_tables(conn)
        conn.execute(
            """INSERT INTO callback_summaries
               (id, callback_id, tenant_id, meeting_notes, outcome, follow_up_required, follow_up_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 meeting_notes=excluded.meeting_notes,
                 outcome=excluded.outcome,
                 follow_up_required=excluded.follow_up_required,
                 follow_up_notes=excluded.follow_up_notes""",
            (
                summary_id,
                payload["callback_id"],
                payload["tenant_id"],
                payload.get("meeting_notes"),
                payload.get("outcome"),
                1 if payload.get("follow_up_required") else 0,
                payload.get("follow_up_notes"),
            ),
        )


def get_callback_summary(callback_id: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("callback_summaries").find_one({"callback_id": callback_id})
        return dict(row) if row else None
    with get_db_context() as conn:
        ensure_callback_tables(conn)
        row = conn.execute(
            "SELECT * FROM callback_summaries WHERE callback_id = ? ORDER BY created_at DESC LIMIT 1",
            (callback_id,),
        ).fetchone()
        return dict(row) if row else None


def list_upcoming_callbacks(tenant_id: str, cutoff_iso: str, limit: int) -> list:
    from services.callback_service import CallbackRequest

    statuses = ("pending", "confirmed", "scheduled")
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("callbacks").find(
            {
                "tenant_id": tenant_id,
                "status": {"$in": list(statuses)},
                "scheduled_start_time": {"$lte": cutoff_iso},
            },
            sort=[("scheduled_start_time", 1)],
            limit=limit,
        )
        out = []
        for row in rows:
            data = row.get("data")
            if isinstance(data, str):
                data = json.loads(data)
            if data:
                out.append(CallbackRequest(**data))
        return out

    with get_db_context() as conn:
        ensure_callback_tables(conn)
        rows = conn.execute(
            """SELECT data FROM callbacks
               WHERE tenant_id = ?
               AND status IN ('pending', 'confirmed', 'scheduled')
               AND scheduled_start_time <= ?
               ORDER BY scheduled_start_time ASC LIMIT ?""",
            (tenant_id, cutoff_iso, limit),
        ).fetchall()
        out = []
        for row in rows:
            if row and row["data"]:
                out.append(CallbackRequest(**json.loads(row["data"])))
        return out


def list_time_slots_rows(tenant_id: str, date: str, agent_id: Optional[str] = None) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        flt: dict[str, Any] = {"tenant_id": tenant_id, "date": date, "is_available": True}
        if agent_id:
            flt["agent_id"] = agent_id
        return [dict(r) for r in Repository("agent_availability").find(flt, sort=[("start_time", 1)])]

    with get_db_context() as conn:
        ensure_callback_tables(conn)
        if agent_id:
            rows = conn.execute(
                """SELECT * FROM agent_availability
                   WHERE tenant_id = ? AND date = ? AND agent_id = ? AND is_available = 1
                   ORDER BY start_time ASC""",
                (tenant_id, date, agent_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM agent_availability
                   WHERE tenant_id = ? AND date = ? AND is_available = 1
                   ORDER BY start_time ASC""",
                (tenant_id, date),
            ).fetchall()
        return [dict(r) for r in rows]


def callback_stats(tenant_id: str, days: int, all_statuses: list[str], all_types: list[str], completed_status: str) -> dict:
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    start_iso = start_date.isoformat()

    if use_mongodb():
        from .mongo import Repository

        repo = Repository("callbacks")
        all_rows = [r for r in repo.find_all({"tenant_id": tenant_id}) if str(r.get("created_at") or "") >= start_iso]
        status_counts = {s: sum(1 for r in all_rows if r.get("status") == s) for s in all_statuses}
        type_counts = {t: 0 for t in all_types}
        for row in all_rows:
            data = row.get("data")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    data = {}
            cb_type = (data or {}).get("callback_type")
            if cb_type in type_counts:
                type_counts[cb_type] += 1
        daily_counts = []
        current = start_date
        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            daily_counts.append({
                "date": date_str,
                "count": sum(1 for r in all_rows if str(r.get("created_at") or "")[:10] == date_str),
            })
            current += timedelta(days=1)
        avg_resolution = None
        completed = [
            r for r in all_rows
            if r.get("status") == completed_status and r.get("scheduled_start_time")
        ]
        if completed:
            deltas = []
            for row in completed:
                try:
                    created = datetime.fromisoformat(str(row.get("created_at")).replace("Z", "+00:00"))
                    updated = datetime.fromisoformat(str(row.get("updated_at")).replace("Z", "+00:00"))
                    deltas.append((updated - created).total_seconds() / 86400.0)
                except Exception:
                    continue
            if deltas:
                avg_resolution = sum(deltas) / len(deltas)
        return {
            "status_counts": status_counts,
            "type_counts": type_counts,
            "daily_counts": daily_counts,
            "avg_resolution": avg_resolution,
            "start_date": start_date,
            "end_date": end_date,
        }

    with get_db_context() as conn:
        ensure_callback_tables(conn)
        status_counts = {}
        for status in all_statuses:
            row = conn.execute(
                """SELECT COUNT(*) as count FROM callbacks
                   WHERE tenant_id = ? AND status = ? AND created_at >= ?""",
                (tenant_id, status, start_iso),
            ).fetchone()
            status_counts[status] = row["count"] if row else 0
        type_counts = {}
        for cb_type in all_types:
            row = conn.execute(
                """SELECT COUNT(*) as count FROM callbacks
                   WHERE tenant_id = ? AND data LIKE ?""",
                (tenant_id, f'%"callback_type":"{cb_type}"%'),
            ).fetchone()
            type_counts[cb_type] = row["count"] if row else 0
        daily_counts = []
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            row = conn.execute(
                """SELECT COUNT(*) as count FROM callbacks
                   WHERE tenant_id = ? AND date(created_at) = ?""",
                (tenant_id, date_str),
            ).fetchone()
            daily_counts.append({"date": date_str, "count": row["count"] if row else 0})
            current_date += timedelta(days=1)
        avg_resolution = None
        row = conn.execute(
            """SELECT AVG(julianday(updated_at) - julianday(created_at)) as days
               FROM callbacks
               WHERE tenant_id = ? AND status = ? AND scheduled_start_time IS NOT NULL""",
            (tenant_id, completed_status),
        ).fetchone()
        if row and row["days"]:
            avg_resolution = float(row["days"])
        return {
            "status_counts": status_counts,
            "type_counts": type_counts,
            "daily_counts": daily_counts,
            "avg_resolution": avg_resolution,
            "start_date": start_date,
            "end_date": end_date,
        }
