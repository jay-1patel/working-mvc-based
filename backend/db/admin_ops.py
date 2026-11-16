"""Admin dashboard, analytics, and chat-history — dual SQLite / Mongo."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .core import get_db, get_db_context, use_mongodb
from .customer_agg import _row_in_window, _since_days, list_global_customers


def _tenant_match(row: dict, tenant_id: Optional[str]) -> bool:
    if not tenant_id:
        return True
    return str(row.get("tenant_id") or "") == str(tenant_id)


def dashboard_stats(*, kb_count: int, faq_count: int, product_count: int) -> dict:
    if use_mongodb():
        from .mongo import Repository

        chats = [
            r for r in Repository("chat_history").find_all({})
            if _row_in_window(r.get("created_at"), 7)
        ]
        grouped: Counter[str] = Counter()
        for row in chats:
            msg = str(row.get("message") or "").lower()
            if msg:
                grouped[msg] += 1
        questions = [
            {"query": q, "count": c}
            for q, c in grouped.most_common(7)
        ]
        wa_sets = set()
        for table in ("orders", "complaints", "user_states"):
            for row in Repository(table).find_all({}):
                wa = str(row.get("wa_id") or "").strip()
                if wa:
                    wa_sets.add(wa)
        total_customers = len(wa_sets)
        orders = Repository("orders").find_all({})
        complaints = Repository("complaints").find_all({})
        total_orders = len(orders)
        orders_solved = sum(
            1 for r in orders if str(r.get("status") or "") in ("delivered", "completed")
        )
        total_complaints = len(complaints)
        complaints_solved = sum(
            1 for r in complaints if str(r.get("status") or "") == "resolved"
        )
    else:
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT message, COUNT(*) as count
                   FROM chat_history
                   WHERE created_at >= DATE('now', '-7 days')
                   GROUP BY LOWER(message)
                   ORDER BY count DESC
                   LIMIT 7""",
            ).fetchall()
            questions = [{"query": r["message"], "count": r["count"]} for r in rows]
            total_customers = (
                conn.execute(
                    """SELECT COUNT(*) AS c FROM (
                           SELECT wa_id FROM orders WHERE wa_id IS NOT NULL
                           UNION
                           SELECT wa_id FROM complaints WHERE wa_id IS NOT NULL
                           UNION
                           SELECT wa_id FROM user_states WHERE wa_id IS NOT NULL
                       )"""
                ).fetchone()["c"]
                or 0
            )
            total_orders = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"] or 0
            orders_solved = (
                conn.execute(
                    "SELECT COUNT(*) AS c FROM orders WHERE status IN ('delivered','completed')"
                ).fetchone()["c"]
                or 0
            )
            total_complaints = conn.execute("SELECT COUNT(*) AS c FROM complaints").fetchone()["c"] or 0
            complaints_solved = (
                conn.execute(
                    "SELECT COUNT(*) AS c FROM complaints WHERE status = 'resolved'"
                ).fetchone()["c"]
                or 0
            )
        finally:
            conn.close()

    return {
        "kb_files": kb_count,
        "faq_files": faq_count,
        "products": product_count,
        "top_questions": questions,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "orders_solved": orders_solved,
        "total_complaints": total_complaints,
        "complaints_solved": complaints_solved,
    }


def admin_list_customers(*, q: str = "", limit: int = 200) -> dict:
    return list_global_customers(q=q, limit=limit)


def admin_chat_history(
    *,
    days: int,
    from_date: Optional[str],
    to_date: Optional[str],
    search: Optional[str],
    tenant_id: Optional[str],
) -> dict:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("chat_history").find_all(
            {},
            sort=[("created_at", -1), ("id", -1)],
            limit=2000,
        )
        if from_date and to_date:
            end = f"{to_date} 23:59:59"
            rows = [
                r for r in rows
                if str(r.get("created_at") or "") >= from_date
                and str(r.get("created_at") or "") <= end
            ]
        else:
            rows = [r for r in rows if _row_in_window(r.get("created_at"), days)]
        if tenant_id:
            rows = [r for r in rows if _tenant_match(r, tenant_id)]
        if search:
            needle = search.lower()
            rows = [
                r for r in rows
                if needle in str(r.get("wa_id") or "").lower()
                or needle in str(r.get("sender_name") or "").lower()
                or needle in str(r.get("message") or "").lower()
                or needle in str(r.get("response") or "").lower()
            ]
        return {"history": [dict(r) for r in rows[:500]]}

    conn = get_db()
    try:
        if from_date and to_date:
            query = """SELECT ch.*
                       FROM chat_history ch
                       WHERE ch.created_at >= ? AND ch.created_at <= ?"""
            params: list = [from_date, to_date + " 23:59:59"]
        else:
            query = """SELECT ch.*
                       FROM chat_history ch
                       WHERE ch.created_at >= DATE('now', ?)"""
            params = [f"-{days} days"]
        if tenant_id:
            query += " AND ch.tenant_id = ?"
            params.append(tenant_id)
        if search:
            query += " AND (ch.wa_id LIKE ? OR ch.sender_name LIKE ? OR ch.message LIKE ? OR ch.response LIKE ?)"
            params.extend([f"%{search}%"] * 4)
        query += " ORDER BY ch.created_at DESC LIMIT 500"
        rows = conn.execute(query, params).fetchall()
        return {"history": [dict(r) for r in rows]}
    finally:
        conn.close()


def _chat_rows(days: int, tenant_id: Optional[str]) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("chat_history").find_all({})
        rows = [r for r in rows if _row_in_window(r.get("created_at"), days)]
        if tenant_id:
            rows = [r for r in rows if _tenant_match(r, tenant_id)]
        return rows
    conn = get_db()
    try:
        sql = "SELECT * FROM chat_history WHERE created_at >= DATE('now', ?)"
        params: list = [f"-{days} days"]
        if tenant_id:
            sql += " AND tenant_id = ?"
            params.append(tenant_id)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _webhook_rows(days: int, tenant_id: Optional[str]) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("webhook_logs").find_all({})
        rows = [r for r in rows if _row_in_window(r.get("created_at"), days)]
        if tenant_id:
            rows = [r for r in rows if _tenant_match(r, tenant_id)]
        return rows
    conn = get_db()
    try:
        sql = (
            "SELECT * FROM webhook_logs WHERE created_at >= DATE('now', ?)"
        )
        params: list = [f"-{days} days"]
        if tenant_id:
            sql += " AND tenant_id = ?"
            params.append(tenant_id)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def analytics_response_time(*, days: int, tenant_id: Optional[str]) -> dict:
    if use_mongodb():
        by_date: dict[str, list[float]] = defaultdict(list)
        for row in _webhook_rows(days, tenant_id):
            if row.get("direction") != "outgoing":
                continue
            ms = row.get("response_time_ms")
            if ms is None:
                continue
            date = str(row.get("created_at") or "")[:10]
            by_date[date].append(float(ms))
        data = [
            {
                "date": d,
                "avg_ms": round(sum(vals) / len(vals), 1) if vals else 0,
                "count": len(vals),
            }
            for d, vals in sorted(by_date.items())
        ]
        return {"days": days, "data": data}

    params: list = [f"-{days} days"]
    tenant_sql = ""
    if tenant_id:
        tenant_sql = " AND tenant_id = ?"
        params.append(tenant_id)
    conn = get_db()
    try:
        rows = conn.execute(
            f"""SELECT DATE(created_at) as date, AVG(response_time_ms) as avg_ms, COUNT(*) as count
               FROM webhook_logs
               WHERE direction = 'outgoing' AND response_time_ms IS NOT NULL
                 AND created_at >= DATE('now', ?)
                 {tenant_sql}
               GROUP BY DATE(created_at)
               ORDER BY date ASC""",
            params,
        ).fetchall()
        return {
            "days": days,
            "data": [
                {
                    "date": r["date"],
                    "avg_ms": round(r["avg_ms"], 1) if r["avg_ms"] else 0,
                    "count": r["count"],
                }
                for r in rows
            ],
        }
    finally:
        conn.close()


def analytics_frequent_questions(*, days: int, limit: int, tenant_id: Optional[str]) -> dict:
    rows = _chat_rows(days, tenant_id)
    grouped: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("message") or "").lower()
        if not key:
            continue
        entry = grouped.setdefault(key, {"query": row.get("message"), "count": 0, "last_asked": ""})
        entry["count"] += 1
        created = str(row.get("created_at") or "")
        if created > entry["last_asked"]:
            entry["last_asked"] = created
    questions = sorted(grouped.values(), key=lambda q: (-q["count"], q["last_asked"]))[:limit]
    return {"days": days, "total_unique": len(questions), "questions": questions}


def analytics_overview(*, days: int, tenant_id: Optional[str]) -> dict:
    chats = _chat_rows(days, tenant_id)
    logs = _webhook_rows(days, tenant_id)
    unique_users = len({str(r.get("wa_id") or "") for r in chats if r.get("wa_id")})
    outgoing = [
        float(r["response_time_ms"])
        for r in logs
        if r.get("direction") == "outgoing" and r.get("response_time_ms") is not None
    ]
    avg_response = sum(outgoing) / len(outgoing) if outgoing else 0
    routes = Counter(str(r.get("route") or "") for r in chats)
    return {
        "days": days,
        "total_messages": len(chats),
        "unique_users": unique_users,
        "avg_response_ms": round(avg_response, 1) if avg_response else 0,
        "route_breakdown": [{"route": k, "count": v} for k, v in routes.items()],
    }


def analytics_top_questions(*, days: int, limit: int, tenant_id: Optional[str]) -> dict:
    rows = _chat_rows(days, tenant_id)
    grouped: Counter[str] = Counter()
    display: dict[str, str] = {}
    for row in rows:
        key = str(row.get("message") or "").lower()
        if not key:
            continue
        grouped[key] += 1
        display.setdefault(key, row.get("message"))
    questions = [
        {"query": display[k], "count": grouped[k]}
        for k, _ in grouped.most_common(limit)
    ]
    total = sum(q["count"] for q in questions)
    return {"days": days, "total": total, "questions": questions}


_UNANSWERED_KEYWORDS = (
    "i don't know", "i do not know", "sorry", "unable to find", "couldn't find",
    "no answer", "not available", "don't have that information",
)


def analytics_unanswered(*, days: int, limit: int, tenant_id: Optional[str]) -> dict:
    rows = _chat_rows(days, tenant_id)
    grouped: dict[str, dict] = {}
    for row in rows:
        response = str(row.get("response") or "").lower()
        if not any(k in response for k in _UNANSWERED_KEYWORDS):
            continue
        key = str(row.get("message") or "").lower()
        if not key:
            continue
        entry = grouped.setdefault(
            key,
            {
                "query": row.get("message"),
                "response": row.get("response"),
                "count": 0,
                "last_asked": "",
            },
        )
        entry["count"] += 1
        created = str(row.get("created_at") or "")
        if created > entry["last_asked"]:
            entry["last_asked"] = created
    queries = sorted(grouped.values(), key=lambda q: (-q["count"], q["last_asked"]))[:limit]
    return {"days": days, "total": len(queries), "queries": queries}


def convert_unanswered_to_faq(
    *,
    query: str,
    answer: str,
    module: str,
    tenant_id: str,
    source_file: str,
) -> int:
    content = f"Q: {query}\nA: {answer}"
    if use_mongodb():
        from .mongo import Repository

        row = Repository("faq_dataset").insert({
            "source_file": source_file,
            "content_type": "text",
            "content": content,
            "page_number": 1,
            "module": module,
            "tenant_id": tenant_id,
        })
        return int(row.get("id") or 0)

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO faq_dataset (source_file, content_type, content, page_number, module, tenant_id) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (source_file, "text", content, module, tenant_id),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_admin_file_row(file_id: int) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("admin_files").find_one({"id": int(file_id)})
        return dict(row) if row else None
    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM admin_files WHERE id = ?", (file_id,)).fetchone()
        return dict(row) if row else None


def delete_admin_file_row(file_id: int) -> bool:
    if use_mongodb():
        from .mongo import Repository

        return Repository("admin_files").delete_one({"id": int(file_id)}) > 0
    with get_db_context() as conn:
        cur = conn.execute("DELETE FROM admin_files WHERE id = ?", (file_id,))
        return cur.rowcount > 0