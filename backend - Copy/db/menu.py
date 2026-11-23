"""Menu items and menu settings data access — extracted from backend/database.py."""
from datetime import datetime, timezone

from .core import logger, get_db_context, use_mongodb


def invalidate_menu_cache():
    """Clear the in-process menu cache (called after admin edits)."""
    try:
        from services.menu_catalog import invalidate_menu_cache as _inv
        _inv()
    except Exception:
        logger.exception("MENU_CACHE_INVALIDATE_FAILED")


def get_menu_items(menu_key: str, active_only: bool = True) -> list:
    """Rows for one menu, ordered. Empty list when menu not in DB."""
    if use_mongodb():
        from .mongo import Repository
        filters = {"menu_key": menu_key}
        if active_only:
            filters["is_active"] = 1
        rows = Repository("menus").find_all(
            filters, sort=[("sort_order", 1), ("id", 1)]
        )
        return [
            {
                "menu_key": r.get("menu_key"),
                "item_id": r.get("item_id"),
                "title": r.get("title"),
                "description": r.get("description"),
                "section": r.get("section"),
                "icon": r.get("icon"),
                "sort_order": r.get("sort_order"),
                "is_active": r.get("is_active"),
            }
            for r in rows
        ]
    sql = ("SELECT menu_key, item_id, title, description, section, icon, "
           "sort_order, is_active FROM menus WHERE menu_key = ?")
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY sort_order ASC, id ASC"
    with get_db_context() as conn:
        rows = conn.execute(sql, (menu_key,)).fetchall()
    return [
        {"menu_key": r[0], "item_id": r[1], "title": r[2], "description": r[3],
         "section": r[4], "icon": r[5], "sort_order": r[6], "is_active": r[7]}
        for r in rows
    ]


def upsert_menu_item(menu_key: str, item_id: str, **fields) -> bool:
    """Insert or update one menu item. item_id/menu_key are immutable keys."""
    allowed = {"title", "description", "section", "icon", "sort_order", "is_active"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return False
    if use_mongodb():
        from .mongo import Repository
        payload = {"menu_key": menu_key, "item_id": item_id, **data,
                   "updated_at": datetime.now(timezone.utc)}
        Repository("menus").upsert({"menu_key": menu_key, "item_id": item_id}, payload)
        return True
    sets = ", ".join(f"{k} = ?" for k in data)
    with get_db_context() as conn:
        conn.execute(
            f"""INSERT INTO menus (menu_key, item_id, {", ".join(data)})
                VALUES (?, ?, {", ".join("?" for _ in data)})
                ON CONFLICT(menu_key, item_id) DO UPDATE SET
                {sets}, updated_at = CURRENT_TIMESTAMP""",
            (menu_key, item_id, *data.values(), *data.values()),
        )
    return True


def reset_menu(menu_key: str) -> int:
    """Delete DB overrides for one menu; loader falls back to code defaults."""
    if use_mongodb():
        from .mongo import Repository
        deleted = Repository("menus").delete_many({"menu_key": menu_key})
        invalidate_menu_cache()
        return deleted
    with get_db_context() as conn:
        cur = conn.execute("DELETE FROM menus WHERE menu_key = ?", (menu_key,))
    invalidate_menu_cache()
    return cur.rowcount


def delete_menu_item(menu_key: str, item_id: str) -> bool:
    """Delete a single menu item row. Returns True if a row was removed."""
    if use_mongodb():
        from .mongo import Repository
        deleted = Repository("menus").delete_one({"menu_key": menu_key, "item_id": item_id})
        invalidate_menu_cache()
        return deleted > 0
    with get_db_context() as conn:
        cur = conn.execute(
            "DELETE FROM menus WHERE menu_key = ? AND item_id = ?",
            (menu_key, item_id),
        )
    invalidate_menu_cache()
    return cur.rowcount > 0


def get_menu_settings(menu_key: str) -> dict:
    if use_mongodb():
        from .mongo import Repository
        row = Repository("menu_settings").find_one({"menu_key": menu_key})
        if not row:
            return {}
        return {
            "header": row.get("header") or "",
            "body": row.get("body") or "",
            "footer": row.get("footer") or "",
            "button_text": row.get("button_text") or "",
        }
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT header, body, footer, button_text FROM menu_settings WHERE menu_key = ?",
            (menu_key,),
        ).fetchone()
    if not row:
        return {}
    return {"header": row[0] or "", "body": row[1] or "",
            "footer": row[2] or "", "button_text": row[3] or ""}


def set_menu_settings(menu_key: str, **fields) -> bool:
    allowed = {"header", "body", "footer", "button_text"}
    data = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not data:
        return False
    if use_mongodb():
        from .mongo import Repository
        payload = {"menu_key": menu_key, **data, "updated_at": datetime.now(timezone.utc)}
        Repository("menu_settings").upsert({"menu_key": menu_key}, payload)
        return True
    cols = ", ".join(data)
    sets = ", ".join(f"{k} = ?" for k in data)
    with get_db_context() as conn:
        conn.execute(
            f"""INSERT INTO menu_settings (menu_key, {cols})
                VALUES (?, {", ".join("?" for _ in data)})
                ON CONFLICT(menu_key) DO UPDATE SET
                {sets}, updated_at = CURRENT_TIMESTAMP""",
            (menu_key, *data.values(), *data.values()),
        )
    return True
