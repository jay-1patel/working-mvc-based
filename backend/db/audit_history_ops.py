"""Admin audit history and audit_logs queries — dual SQLite / Mongo."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from .core import get_db, use_mongodb
from .audit import safe_audit_details


def _year_cutoff_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()


def _matches_admin_audit_row(
    row: dict,
    *,
    start_date: Optional[date],
    end_date: Optional[date],
    actor: Optional[str],
    action: Optional[str],
    category_actions: Optional[list[str]],
    tenant_id: Optional[str],
    outcome: Optional[str],
    search: Optional[str],
    actor_roles: Optional[list[str]],
) -> bool:
    created = str(row.get("created_at") or "")
    if created < _year_cutoff_iso()[:19]:
        return False
    if start_date and created[:10] < start_date.isoformat():
        return False
    if end_date and created[:10] > end_date.isoformat():
        return False
    if actor and actor.strip():
        if actor.strip().lower() not in str(row.get("actor_username") or "").lower():
            return False
    if action and str(row.get("action") or "") != action.strip():
        return False
    if tenant_id and str(row.get("tenant_id") or "") != str(tenant_id):
        return False
    if outcome and str(row.get("outcome") or "") != outcome.strip():
        return False
    if category_actions and str(row.get("action") or "") not in category_actions:
        return False
    if actor_roles is not None:
        role = str(row.get("actor_role") or "").strip().lower()
        if role not in {r.lower() for r in actor_roles}:
            return False
    if search and search.strip():
        term = search.strip().lower()
        haystacks = [
            row.get("actor_username"),
            row.get("actor_label"),
            row.get("target_username"),
            row.get("resource_type"),
            row.get("resource_id"),
            row.get("action"),
            row.get("tenant_id"),
            row.get("tenant_name"),
            row.get("tenant_slug"),
            row.get("ip_address"),
            row.get("user_agent"),
            row.get("details_json"),
        ]
        if not any(term in str(h or "").lower() for h in haystacks):
            return False
    return True


def _format_audit_event(row: dict) -> dict:
    event = dict(row)
    details_raw = event.pop("details_json", None) if "details_json" in event else event.get("details")
    try:
        if isinstance(details_raw, str):
            event["details"] = safe_audit_details(json.loads(details_raw or "{}"))
        elif isinstance(details_raw, dict):
            event["details"] = safe_audit_details(details_raw)
        else:
            event["details"] = {}
    except (json.JSONDecodeError, TypeError):
        event["details"] = {}
    event["tenant_label"] = " · ".join(
        part for part in (event.get("tenant_name"), event.get("tenant_slug"), event.get("tenant_id")) if part
    ) or "Platform"
    return event


def list_admin_audit_events(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    category_actions: Optional[list[str]] = None,
    tenant_id: Optional[str] = None,
    outcome: Optional[str] = None,
    search: Optional[str] = None,
    actor_roles: Optional[list[str]] = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict:
    reverse = (sort_order or "desc").lower() != "asc"
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("admin_audit_events").find_all(
            {}, sort=[("created_at", -1), ("id", -1)], limit=None,
        )
        filtered = [
            r for r in rows
            if _matches_admin_audit_row(
                r,
                start_date=start_date,
                end_date=end_date,
                actor=actor,
                action=action,
                category_actions=category_actions,
                tenant_id=tenant_id,
                outcome=outcome,
                search=search,
                actor_roles=actor_roles,
            )
        ]
        if sort_by:
            filtered.sort(key=lambda r: (r.get(sort_by), r.get("id")), reverse=reverse)
        total = len(filtered)
        page = filtered[offset: offset + limit]
        events = [_format_audit_event(dict(r)) for r in page]
        return {"events": events, "total": total, "limit": limit, "offset": offset}

    where = ["datetime(created_at) >= datetime('now', '-365 days')"]
    params: list = []
    if start_date:
        where.append("date(created_at) >= ?")
        params.append(start_date.isoformat())
    if end_date:
        where.append("date(created_at) <= ?")
        params.append(end_date.isoformat())
    if actor and actor.strip():
        where.append("actor_username LIKE ?")
        params.append(f"%{actor.strip()}%")
    if action:
        where.append("action = ?")
        params.append(action.strip())
    if tenant_id:
        where.append("tenant_id = ?")
        params.append(tenant_id.strip())
    if outcome:
        where.append("outcome = ?")
        params.append(outcome.strip())
    if category_actions:
        where.append(f"action IN ({', '.join('?' for _ in category_actions)})")
        params.extend(category_actions)
    if actor_roles is not None:
        placeholders = ", ".join("?" for _ in actor_roles)
        where.append(f"LOWER(COALESCE(actor_role, '')) IN ({placeholders})")
        params.extend(actor_roles)
    if search and search.strip():
        term = f"%{search.strip()}%"
        where.append(
            "(actor_username LIKE ? OR actor_label LIKE ? OR target_username LIKE ? OR "
            "resource_type LIKE ? OR resource_id LIKE ? OR action LIKE ? OR tenant_id LIKE ? OR "
            "tenant_name LIKE ? OR tenant_slug LIKE ? OR ip_address LIKE ? OR user_agent LIKE ? OR details_json LIKE ?)"
        )
        params.extend([term] * 12)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    conn = get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM admin_audit_events{clause}", params).fetchone()[0]
        sort_column = sort_by or "created_at"
        rows = conn.execute(
            f"""SELECT id, created_at, actor_id, actor_username, actor_role,
                       action, outcome, resource_type, resource_id, target_username,
                       tenant_id, tenant_name, tenant_slug, actor_kind, actor_label,
                       details_json, ip_address, user_agent
                FROM admin_audit_events{clause}
                ORDER BY {sort_column} {sort_order or 'desc'}, id DESC LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
    finally:
        conn.close()
    events = [_format_audit_event(dict(r)) for r in rows]
    return {"events": events, "total": total, "limit": limit, "offset": offset}


def admin_audit_statistics(**kwargs) -> dict:
    result = list_admin_audit_events(limit=100000, offset=0, **kwargs)
    events = result["events"]
    by_outcome = {"success": 0, "failure": 0}
    by_action: dict[str, int] = {}
    by_date: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    category_map = kwargs.get("category_map") or {}
    by_category: dict = {}
    for event in events:
        outcome = event.get("outcome")
        if outcome in by_outcome:
            by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        act = str(event.get("action") or "")
        by_action[act] = by_action.get(act, 0) + 1
        day = str(event.get("created_at") or "")[:10]
        if day:
            by_date[day] = by_date.get(day, 0) + 1
        actor_name = event.get("actor_username") or "unknown"
        by_actor[actor_name] = by_actor.get(actor_name, 0) + 1
        cat = category_map.get(act, "other")
        by_category[cat] = by_category.get(cat, 0) + 1
    return {
        "total_events": len(events),
        "by_outcome": by_outcome,
        "by_action": by_action,
        "by_date": by_date,
        "by_category": by_category,
        "by_actor": by_actor,
    }


def get_admin_audit_event(event_id: int) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("admin_audit_events").find_one({"id": int(event_id)})
        return _format_audit_event(dict(row)) if row else None
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT id, created_at, actor_id, actor_username, actor_role, action, outcome,
                      resource_type, resource_id, target_username, tenant_id, tenant_name,
                      tenant_slug, actor_kind, actor_label, details_json, ip_address, user_agent
               FROM admin_audit_events WHERE id = ?""",
            [event_id],
        ).fetchone()
        return _format_audit_event(dict(row)) if row else None
    finally:
        conn.close()


def _audit_log_matches(row: dict, *, start_iso: str, end_iso: str, search, actor, action, category) -> bool:
    created = str(row.get("created_at") or "")
    if created < start_iso or created > end_iso:
        return False
    if search and search.strip():
        term = search.strip().lower()
        if term not in str(row.get("description") or "").lower() and term not in str(row.get("metadata") or "").lower():
            return False
    if actor and str(row.get("actor") or "") != actor.strip():
        return False
    if action and str(row.get("action") or "") != action.strip():
        return False
    if category and str(row.get("category") or "") != category.strip():
        return False
    return True


def list_audit_logs(
    *,
    start_iso: str,
    end_iso: str,
    search: Optional[str] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("audit_logs").find_all({}, sort=[("created_at", -1), ("id", -1)])
        filtered = [
            r for r in rows
            if _audit_log_matches(
                r,
                start_iso=start_iso,
                end_iso=end_iso,
                search=search,
                actor=actor,
                action=action,
                category=category,
            )
        ]
        total = len(filtered)
        page = filtered[offset: offset + limit]
        events = []
        for row in page:
            event = dict(row)
            event["timestamp"] = event.get("created_at")
            if event.get("metadata") and isinstance(event["metadata"], str):
                try:
                    event["metadata"] = json.loads(event["metadata"])
                except (json.JSONDecodeError, TypeError):
                    event["metadata"] = {}
            events.append(event)
        return {"events": events, "total": total, "limit": limit, "offset": offset}

    conn = get_db()
    try:
        where_clauses = ["created_at >= ? AND created_at <= ?"]
        params: list = [start_iso, end_iso]
        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append("(description LIKE ? OR metadata LIKE ?)")
            params.extend([term, term])
        if actor and actor.strip():
            where_clauses.append("actor = ?")
            params.append(actor.strip())
        if action and action.strip():
            where_clauses.append("action = ?")
            params.append(action.strip())
        if category and category.strip():
            where_clauses.append("category = ?")
            params.append(category.strip())
        where_clause = " AND ".join(where_clauses)
        query = f"""
            SELECT id, created_at as timestamp, actor, action, category, status, description, metadata
            FROM audit_logs
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        count_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
        total_count = conn.execute(count_query, params[:-2]).fetchone()[0]
        events = []
        for row in rows:
            event = dict(row)
            if event.get("metadata"):
                try:
                    event["metadata"] = json.loads(event["metadata"])
                except (json.JSONDecodeError, TypeError):
                    event["metadata"] = {}
            events.append(event)
        return {"events": events, "total": total_count, "limit": limit, "offset": offset}
    finally:
        conn.close()


def audit_logs_statistics(*, start_iso: str, end_iso: str) -> dict:
    if use_mongodb():
        from .mongo import Repository

        rows = [
            r for r in Repository("audit_logs").find_all({})
            if start_iso <= str(r.get("created_at") or "") <= end_iso
        ]
        by_status: dict = {}
        by_category: dict = {}
        by_action: dict = {}
        by_actor: dict = {}
        by_date: dict = {}
        for row in rows:
            by_status[row.get("status")] = by_status.get(row.get("status"), 0) + 1
            by_category[row.get("category")] = by_category.get(row.get("category"), 0) + 1
            by_action[row.get("action")] = by_action.get(row.get("action"), 0) + 1
            by_actor[row.get("actor")] = by_actor.get(row.get("actor"), 0) + 1
            day = str(row.get("created_at") or "")[:10]
            by_date[day] = by_date.get(day, 0) + 1
        return {
            "total_events": len(rows),
            "by_status": by_status,
            "by_category": by_category,
            "by_action": by_action,
            "by_actor": by_actor,
            "by_date": by_date,
        }

    conn = get_db()
    try:
        params = [start_iso, end_iso]
        total = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE created_at >= ? AND created_at <= ?",
            params,
        ).fetchone()[0]
        def group(col):
            return {
                row[0]: row[1]
                for row in conn.execute(
                    f"SELECT {col}, COUNT(*) as count FROM audit_logs WHERE created_at >= ? AND created_at <= ? GROUP BY {col}",
                    params,
                ).fetchall()
            }
        by_date = {
            row[0]: row[1]
            for row in conn.execute(
                """SELECT date(created_at) as date, COUNT(*) as count
                   FROM audit_logs WHERE created_at >= ? AND created_at <= ?
                   GROUP BY date(created_at) ORDER BY date(created_at)""",
                params,
            ).fetchall()
        }
        return {
            "total_events": total,
            "by_status": group("status"),
            "by_category": group("category"),
            "by_action": group("action"),
            "by_actor": group("actor"),
            "by_date": by_date,
        }
    finally:
        conn.close()