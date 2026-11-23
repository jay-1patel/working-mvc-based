"""LIKE-style FAQ/KB keyword search data access — extracted from backend/database.py."""
import re as _re

from .core import get_db_context, use_mongodb
from .products import _resolve_tenant, _row_to_dict


def _tenant_ids(effective_tid):
    t_id_str = None
    t_slug = None
    if effective_tid:
        try:
            from shared.tenancy import store
            rec = store.get_tenant(str(effective_tid))
            if rec:
                t_id_str = str(rec.get("id"))
                t_slug = str(rec.get("slug"))
            else:
                t_id_str = str(effective_tid)
                t_slug = str(effective_tid)
        except Exception:
            t_id_str = str(effective_tid)
            t_slug = str(effective_tid)
    return t_id_str, t_slug


def _mongo_tenant_filter(t_id_str, t_slug, effective_tid):
    values = []
    for v in (t_id_str, t_slug, str(effective_tid) if effective_tid else None):
        if v is None or v == "":
            continue
        values.append(v)
        if isinstance(v, str) and v.isdigit():
            values.append(int(v))
    if not values:
        return {}
    # de-dupe while preserving order
    seen = set()
    uniq = []
    for v in values:
        key = (type(v), v)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)
    return {"tenant_id": {"$in": uniq}}


def search_faq_db(query: str, limit: int = 5, tenant_id: str = None) -> list:
    words = [w for w in _re.findall(r"[a-zA-Z]{2,}", query.lower())]
    if not words:
        return []

    effective_tid = tenant_id or _resolve_tenant()
    t_id_str, t_slug = _tenant_ids(effective_tid)

    if use_mongodb():
        from .mongo import Repository
        repo = Repository("faq_dataset")
        filters = {"content": {"$regex": _re.escape(query), "$options": "i"}}
        filters.update(_mongo_tenant_filter(t_id_str, t_slug, effective_tid))
        rows = repo.find(filters, sort=[("id", -1)], limit=limit)
        if rows:
            return [dict(r) for r in rows]
        all_rows = repo.find_all()
        scored = []
        allowed_tids = {t_id_str, t_slug, str(effective_tid)} if effective_tid else set()
        for d in all_rows:
            row_tid = str(d.get("tenant_id") or "")
            if allowed_tids and row_tid not in allowed_tids:
                continue
            searchable = " ".join([
                (d.get("source_file") or "").lower(),
                (d.get("content") or "").lower(),
            ])
            score = sum(2 for w in words if w in searchable)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    if t_id_str and t_slug and t_id_str != t_slug:
        tenant_clause = " AND (tenant_id = ? OR tenant_id = ? OR tenant_id = ?)"
        tenant_params = [t_id_str, int(t_id_str) if t_id_str.isdigit() else t_id_str, t_slug]
    elif t_id_str:
        tenant_clause = " AND (tenant_id = ? OR tenant_id = ?)"
        tenant_params = [t_id_str, int(t_id_str) if t_id_str.isdigit() else t_id_str]
    else:
        tenant_clause = ""
        tenant_params = []

    with get_db_context() as conn:
        rows = conn.execute(
            f"""SELECT * FROM faq_dataset
               WHERE content LIKE ?{tenant_clause}
               ORDER BY id DESC LIMIT ?""",
            ([f"%{query}%"] + tenant_params + [limit]),
        ).fetchall()
        if rows:
            return [_row_to_dict(r) for r in rows]
        all_rows = conn.execute("SELECT * FROM faq_dataset").fetchall()
        scored = []
        allowed_tids = {t_id_str, t_slug, str(effective_tid)} if effective_tid else set()
        for r in all_rows:
            d = _row_to_dict(r)
            row_tid = str(d.get("tenant_id") or "")
            if allowed_tids and row_tid not in allowed_tids:
                continue
            searchable = " ".join([
                (d.get("source_file") or "").lower(),
                (d.get("content") or "").lower(),
            ])
            score = sum(2 for w in words if w in searchable)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]


def search_knowledge_base_db(query: str, limit: int = 5, tenant_id: str = None) -> list:
    words = [w for w in _re.findall(r"[a-zA-Z]{2,}", query.lower())]
    if not words:
        return []

    effective_tid = tenant_id or _resolve_tenant()
    t_id_str, t_slug = _tenant_ids(effective_tid)

    if use_mongodb():
        from .mongo import Repository
        repo = Repository("knowledge_base")
        pattern = _re.escape(query)
        filters = {"$or": [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"content": {"$regex": pattern, "$options": "i"}},
            {"tags": {"$regex": pattern, "$options": "i"}},
        ]}
        filters.update(_mongo_tenant_filter(t_id_str, t_slug, effective_tid))
        rows = repo.find(filters, sort=[("id", -1)], limit=limit)
        if rows:
            return [dict(r) for r in rows]
        all_rows = repo.find_all()
        scored = []
        allowed_tids = {t_id_str, t_slug, str(effective_tid)} if effective_tid else set()
        for d in all_rows:
            row_tid = str(d.get("tenant_id") or "")
            if allowed_tids and row_tid not in allowed_tids:
                continue
            tags = d.get("tags") or ""
            if isinstance(tags, (list, dict)):
                tags = str(tags)
            searchable = " ".join([
                (d.get("title") or "").lower(),
                (d.get("content") or "").lower(),
                tags.lower(),
            ])
            score = sum(2 for w in words if w in searchable)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    if t_id_str and t_slug and t_id_str != t_slug:
        tenant_clause = " AND (tenant_id = ? OR tenant_id = ? OR tenant_id = ?)"
        tenant_params = [t_id_str, int(t_id_str) if t_id_str.isdigit() else t_id_str, t_slug]
    elif t_id_str:
        tenant_clause = " AND (tenant_id = ? OR tenant_id = ?)"
        tenant_params = [t_id_str, int(t_id_str) if t_id_str.isdigit() else t_id_str]
    else:
        tenant_clause = ""
        tenant_params = []

    with get_db_context() as conn:
        rows = conn.execute(
            f"""SELECT * FROM knowledge_base
               WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?){tenant_clause}
               ORDER BY id DESC LIMIT ?""",
            ([f"%{query}%", f"%{query}%", f"%{query}%"] + tenant_params + [limit]),
        ).fetchall()
        if rows:
            return [_row_to_dict(r) for r in rows]
        all_rows = conn.execute("SELECT * FROM knowledge_base").fetchall()
        scored = []
        allowed_tids = {t_id_str, t_slug, str(effective_tid)} if effective_tid else set()
        for r in all_rows:
            d = _row_to_dict(r)
            row_tid = str(d.get("tenant_id") or "")
            if allowed_tids and row_tid not in allowed_tids:
                continue
            searchable = " ".join([
                (d.get("title") or "").lower(),
                (d.get("content") or "").lower(),
                (d.get("tags") or "").lower(),
            ])
            score = sum(2 for w in words if w in searchable)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]
