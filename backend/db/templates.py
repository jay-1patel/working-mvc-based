"""Message templates and session buttons data access — extracted from backend/database.py."""
import json
from datetime import datetime, timezone

from .core import logger, get_db_context, use_mongodb, _loads_json


def _as_list(value):
    if isinstance(value, list):
        return value
    return _loads_json(value, [])


def _as_dict(value):
    if isinstance(value, dict):
        return value
    return _loads_json(value, {})


def save_template(name: str, data: dict) -> int:
    payload = {
        "name": name,
        "category": data.get("category", "UTILITY"),
        "subcategory": data.get("subcategory", "custom"),
        "header_type": data.get("header_type", "noheader"),
        "header_text": data.get("header_text", ""),
        "body_template": data.get("body_template", ""),
        "footer": data.get("footer", ""),
        "buttons_json": data.get("buttons", []),
        "params_json": data.get("params", []),
        "language": data.get("language", "en"),
        "template_for": data.get("template_for", "sales"),
        "status": data.get("status", "registered"),
        "send2_response": data.get("send2_response", ""),
        "updated_at": datetime.now(timezone.utc),
    }
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("whatsapp_templates")
        existing = repo.find_one({"name": name})
        if existing:
            repo.update({"name": name}, payload)
            return existing["id"]
        row = repo.insert(payload)
        return int(row["id"])
    with get_db_context() as conn:
        existing = conn.execute(
            "SELECT id FROM whatsapp_templates WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE whatsapp_templates SET
                    category = ?, subcategory = ?, header_type = ?,
                    header_text = ?, body_template = ?, footer = ?,
                    buttons_json = ?, params_json = ?, language = ?,
                    template_for = ?, status = ?, send2_response = ?,
                    updated_at = CURRENT_TIMESTAMP
                   WHERE name = ?""",
                (
                    data.get("category", "UTILITY"),
                    data.get("subcategory", "custom"),
                    data.get("header_type", "noheader"),
                    data.get("header_text", ""),
                    data.get("body_template", ""),
                    data.get("footer", ""),
                    json.dumps(data.get("buttons", [])),
                    json.dumps(data.get("params", [])),
                    data.get("language", "en"),
                    data.get("template_for", "sales"),
                    data.get("status", "registered"),
                    data.get("send2_response", ""),
                    name,
                ),
            )
            return existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO whatsapp_templates
                    (name, category, subcategory, header_type, header_text,
                     body_template, footer, buttons_json, params_json,
                     language, template_for, status, send2_response)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    data.get("category", "UTILITY"),
                    data.get("subcategory", "custom"),
                    data.get("header_type", "noheader"),
                    data.get("header_text", ""),
                    data.get("body_template", ""),
                    data.get("footer", ""),
                    json.dumps(data.get("buttons", [])),
                    json.dumps(data.get("params", [])),
                    data.get("language", "en"),
                    data.get("template_for", "sales"),
                    data.get("status", "registered"),
                    data.get("send2_response", ""),
                ),
            )
            return cur.lastrowid


def get_template(name: str) -> dict:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("whatsapp_templates").find_one({"name": name})
        if not row:
            return None
        result = dict(row)
        result["buttons_json"] = _as_list(result.get("buttons_json"))
        result["params_json"] = _as_list(result.get("params_json"))
        return result
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM whatsapp_templates WHERE name = ?", (name,)
        ).fetchone()
    if row:
        result = dict(row)
        try:
            result["buttons_json"] = json.loads(result.get("buttons_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            result["buttons_json"] = []
        try:
            result["params_json"] = json.loads(result.get("params_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            result["params_json"] = []
        return result
    return None


def list_templates(status: str = None, category: str = None, limit: int = 50) -> list:
    if use_mongodb():
        from .mongo import Repository
        filters = {}
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        rows = Repository("whatsapp_templates").find(
            filters, sort=[("updated_at", -1)], limit=limit
        )
        results = []
        for r in rows:
            d = dict(r)
            d["buttons_json"] = _as_list(d.get("buttons_json"))
            results.append(d)
        return results
    query = "SELECT * FROM whatsapp_templates WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with get_db_context() as conn:
        rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["buttons_json"] = json.loads(d.get("buttons_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["buttons_json"] = []
        results.append(d)
    return results


def delete_template(name: str) -> bool:
    if use_mongodb():
        from .mongo import Repository
        Repository("whatsapp_templates").delete_one({"name": name})
        return True
    with get_db_context() as conn:
        conn.execute("DELETE FROM whatsapp_templates WHERE name = ?", (name,))
    return True


def save_session_button(button_id: str, wa_id: str = None, session_id: str = None,
                        button_type: str = "quick", label: str = "",
                        payload: dict = None, state: str = "MAIN_MENU",
                        lang: str = "en", expires_at: str = None) -> int:
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("session_buttons")
        existing = repo.find_one({"button_id": button_id})
        changes = {
            "button_id": button_id,
            "wa_id": wa_id,
            "session_id": session_id,
            "button_type": button_type,
            "label": label,
            "payload_json": payload or {},
            "state": state,
            "lang": lang,
            "expires_at": expires_at,
            "is_active": 1,
            "triggered_at": None,
        }
        if existing:
            repo.update({"button_id": button_id}, changes)
            return existing["id"]
        row = repo.insert(changes)
        return int(row["id"])
    payload_json = json.dumps(payload or {})
    with get_db_context() as conn:
        existing = conn.execute(
            "SELECT id FROM session_buttons WHERE button_id = ?", (button_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE session_buttons SET
                    wa_id = ?, session_id = ?, button_type = ?, label = ?,
                    payload_json = ?, state = ?, lang = ?,
                    expires_at = ?, is_active = 1, triggered_at = NULL
                   WHERE button_id = ?""",
                (wa_id, session_id, button_type, label, payload_json,
                 state, lang, expires_at, button_id),
            )
            return existing["id"]
        else:
            cur = conn.execute(
                """INSERT INTO session_buttons
                    (button_id, wa_id, session_id, button_type, label,
                     payload_json, state, lang, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (button_id, wa_id, session_id, button_type, label,
                 payload_json, state, lang, expires_at),
            )
            return cur.lastrowid


def get_session_button(button_id: str) -> dict:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("session_buttons").find_one({"button_id": button_id})
        if not row:
            return None
        result = dict(row)
        result["payload_json"] = _as_dict(result.get("payload_json"))
        return result
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT * FROM session_buttons WHERE button_id = ?", (button_id,)
        ).fetchone()
    if row:
        result = dict(row)
        try:
            result["payload_json"] = json.loads(result.get("payload_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            result["payload_json"] = {}
        return result
    return None


def list_session_buttons(wa_id: str = None, state: str = None,
                         is_active: bool = True, limit: int = 50) -> list:
    if use_mongodb():
        from .mongo import Repository
        filters = {}
        if wa_id:
            filters["wa_id"] = wa_id
        if state:
            filters["state"] = state
        if is_active:
            filters["is_active"] = 1
        rows = Repository("session_buttons").find(
            filters, sort=[("created_at", -1)], limit=limit
        )
        results = []
        for r in rows:
            d = dict(r)
            d["payload_json"] = _as_dict(d.get("payload_json"))
            results.append(d)
        return results
    query = "SELECT * FROM session_buttons WHERE 1=1"
    params = []
    if wa_id:
        query += " AND wa_id = ?"
        params.append(wa_id)
    if state:
        query += " AND state = ?"
        params.append(state)
    if is_active:
        query += " AND is_active = 1"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db_context() as conn:
        rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["payload_json"] = json.loads(d.get("payload_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["payload_json"] = {}
        results.append(d)
    return results


def deactivate_session_button(button_id: str) -> bool:
    if use_mongodb():
        from .mongo import Repository
        Repository("session_buttons").update({"button_id": button_id}, {"is_active": 0})
        return True
    with get_db_context() as conn:
        conn.execute(
            "UPDATE session_buttons SET is_active = 0 WHERE button_id = ?",
            (button_id,),
        )
    return True


def trigger_session_button(button_id: str, wa_id: str) -> bool:
    if use_mongodb():
        from .mongo import Repository
        Repository("session_buttons").update(
            {"button_id": button_id},
            {"triggered_at": datetime.now(timezone.utc)},
        )
        return True
    with get_db_context() as conn:
        conn.execute(
            "UPDATE session_buttons SET triggered_at = CURRENT_TIMESTAMP WHERE button_id = ?",
            (button_id,),
        )
    return True


def log_button_click(button_id: str, wa_id: str, session_id: str = None,
                     button_type: str = None, label: str = None,
                     payload: dict = None, source: str = "whatsapp",
                     metadata: dict = None) -> int:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("button_clicks").insert({
            "button_id": button_id,
            "wa_id": wa_id,
            "session_id": session_id,
            "button_type": button_type,
            "label": label,
            "payload_json": payload or {},
            "source": source,
            "metadata_json": metadata or {},
        })
        return int(row["id"])
    with get_db_context() as conn:
        cur = conn.execute(
            """INSERT INTO button_clicks
                (button_id, wa_id, session_id, button_type, label,
                 payload_json, source, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (button_id, wa_id, session_id, button_type, label,
             json.dumps(payload or {}), source, json.dumps(metadata or {})),
        )
        return cur.lastrowid


def get_button_clicks(button_id: str = None, wa_id: str = None,
                      limit: int = 50) -> list:
    if use_mongodb():
        from .mongo import Repository
        filters = {}
        if button_id:
            filters["button_id"] = button_id
        if wa_id:
            filters["wa_id"] = wa_id
        rows = Repository("button_clicks").find(
            filters, sort=[("created_at", -1)], limit=limit
        )
        results = []
        for r in rows:
            d = dict(r)
            d["payload_json"] = _as_dict(d.get("payload_json"))
            d["metadata_json"] = _as_dict(d.get("metadata_json"))
            results.append(d)
        return results
    query = "SELECT * FROM button_clicks WHERE 1=1"
    params = []
    if button_id:
        query += " AND button_id = ?"
        params.append(button_id)
    if wa_id:
        query += " AND wa_id = ?"
        params.append(wa_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db_context() as conn:
        rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["payload_json"] = json.loads(d.get("payload_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["payload_json"] = {}
        try:
            d["metadata_json"] = json.loads(d.get("metadata_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["metadata_json"] = {}
        results.append(d)
    return results


def get_button_click_stats(button_id: str = None, wa_id: str = None) -> dict:
    if use_mongodb():
        from .mongo import get_database
        match = {}
        if button_id:
            match["button_id"] = button_id
        if wa_id:
            match["wa_id"] = wa_id
        pipeline = [
            {"$match": match} if match else {"$match": {}},
            {"$group": {
                "_id": {"button_id": "$button_id", "label": "$label"},
                "total": {"$sum": 1},
            }},
            {"$project": {
                "_id": 0,
                "button_id": "$_id.button_id",
                "label": "$_id.label",
                "total": 1,
            }},
            {"$sort": {"total": -1}},
        ]
        rows = list(get_database()["button_clicks"].aggregate(pipeline))
        return {"total_clicks": sum(r["total"] for r in rows), "by_button": rows}
    query = "SELECT COUNT(*) as total, button_id, label FROM button_clicks WHERE 1=1"
    params = []
    if button_id:
        query += " AND button_id = ?"
        params.append(button_id)
    if wa_id:
        query += " AND wa_id = ?"
        params.append(wa_id)
    query += " GROUP BY button_id, label ORDER BY total DESC"
    with get_db_context() as conn:
        rows = conn.execute(query, params).fetchall()
    return {"total_clicks": sum(r["total"] for r in rows), "by_button": [dict(r) for r in rows]}
