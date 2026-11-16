"""Chat history, embeddings and KB chunk storage data access — extracted from backend/database.py."""
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from .core import (
    logger, get_db_context, use_mongodb, _current_tenant,
)
from .products import _resolve_tenant


def _parse_history_ts(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(text[:26].replace("Z", ""), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        return None


def save_chat(wa_id, sender_name, message, response, route="faq", tenant_id=None):
    tid = tenant_id or _current_tenant.get() or _resolve_tenant()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stored_message = f"[{route}] {message}"
    if use_mongodb():
        from .mongo import Repository
        Repository("chat_history").insert({
            "wa_id": wa_id,
            "sender_name": sender_name,
            "message": stored_message,
            "response": response,
            "route": route,
            "tenant_id": tid,
            "created_at": created_at,
        })
    else:
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO chat_history (wa_id, sender_name, message, response, route, tenant_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (wa_id, sender_name, stored_message, response, route, tid, created_at),
            )
    # Mirror every exchange into a per-tenant, per-day JSON audit file,
    # alongside (never instead of) the DB row above.
    try:
        try:
            from json_history import append_chat as _json_append
        except ImportError:
            from backend.json_history import append_chat as _json_append
        _json_append(wa_id, sender_name, stored_message, response, route, tid, created_at)
    except Exception as e:
        logger.warning(f"json_history mirror failed for {wa_id}: {e}")


def list_chat_thread(wa_id: str, *, tenant_id: Optional[str] = None, limit: int = 200) -> list:
    """Chat history rows for the admin thread view (user + bot messages)."""
    if use_mongodb():
        from .mongo import Repository
        flt: dict = {"wa_id": wa_id}
        if tenant_id:
            flt["tenant_id"] = tenant_id
        rows = Repository("chat_history").find(
            flt, sort=[("id", 1)], limit=limit
        )
        return [dict(r) for r in rows]
    with get_db_context() as conn:
        if tenant_id:
            rows = conn.execute(
                """
                SELECT id, wa_id, sender_name, message, response, route, created_at
                FROM chat_history
                WHERE wa_id = ? AND tenant_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (wa_id, tenant_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, wa_id, sender_name, message, response, route, created_at
                FROM chat_history
                WHERE wa_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (wa_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def get_recent_history(
    wa_id: str,
    limit: int = 5,
    ttl_minutes: int = 30,
    tenant_id: Optional[str] = None,
):
    tid = tenant_id or _current_tenant.get() or _resolve_tenant()
    if use_mongodb():
        from .mongo import Repository
        filters = {"wa_id": wa_id}
        if tid:
            filters["tenant_id"] = tid
        rows = Repository("chat_history").find(
            filters, sort=[("created_at", -1)], limit=limit
        )
        rows = list(reversed(rows))
    else:
        with get_db_context() as conn:
            if tid:
                rows = conn.execute(
                    "SELECT message, response, created_at FROM chat_history "
                    "WHERE tenant_id = ? AND wa_id = ? ORDER BY created_at DESC LIMIT ?",
                    (tid, wa_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT message, response, created_at FROM chat_history "
                    "WHERE wa_id = ? ORDER BY created_at DESC LIMIT ?",
                    (wa_id, limit),
                ).fetchall()
        if not rows:
            return []
        rows = list(reversed(rows))
    if not rows:
        return []
    last = rows[-1]
    try:
        now = datetime.now(timezone.utc)
        last_time = _parse_history_ts(last["created_at"] if hasattr(last, "keys") else last.get("created_at"))
        if last_time and (now - last_time).total_seconds() > ttl_minutes * 60:
            return []
    except Exception:
        # deliberate: an unparseable timestamp must not hide history —
        # the rows are returned without the TTL cut.
        logger.debug("HISTORY_TTL_CHECK_SKIPPED", exc_info=True)
    out = []
    for row in rows:
        raw_user = (row["message"] if hasattr(row, "keys") else row.get("message")) or ""
        # Strip internal route prefixes like [send2], [webhook], [faq]
        clean_user = re.sub(r"^\[[\w\-/]+\]\s*", "", raw_user).strip()
        resp = row["response"] if hasattr(row, "keys") else row.get("response")
        out.append({"user": clean_user, "assistant": resp or ""})
    return out


def save_embeddings(embedding_data):
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("faq_dataset")
        for faq_id, embedding_bytes in embedding_data:
            repo.update({"id": faq_id}, {"embedding": embedding_bytes})
        return
    with get_db_context() as conn:
        for faq_id, embedding_bytes in embedding_data:
            conn.execute(
                "UPDATE faq_dataset SET embedding = ? WHERE id = ?",
                (embedding_bytes, faq_id),
            )


def save_chunks(chunks, module="faq", media_url=None, media_type=None, tenant_id=None, replace_existing=False):
    """Insert FAQ/document chunks. When replace_existing=True, delete prior rows
    for each distinct source_file (+ tenant) before inserting — prevents duplicate
    vectors on re-upload.
    """
    if use_mongodb():
        from .mongo import Repository
        repo = Repository("faq_dataset")
        if replace_existing:
            sources = {chunk.get("source_file") for chunk in chunks if chunk.get("source_file")}
            for src in sources:
                filters = {"source_file": src}
                if tenant_id is not None:
                    filters["tenant_id"] = tenant_id
                repo.delete_many(filters)
        for chunk in chunks:
            repo.insert({
                "source_file": chunk["source_file"],
                "content_type": chunk["content_type"],
                "content": chunk["content"],
                "page_number": chunk["page_number"],
                "module": module,
                "media_url": media_url,
                "media_type": media_type,
                "tenant_id": tenant_id,
            })
        return
    with get_db_context() as conn:
        if replace_existing:
            sources = {chunk.get("source_file") for chunk in chunks if chunk.get("source_file")}
            for src in sources:
                if tenant_id is not None:
                    conn.execute(
                        "DELETE FROM faq_dataset WHERE source_file = ? AND tenant_id = ?",
                        (src, tenant_id),
                    )
                else:
                    conn.execute("DELETE FROM faq_dataset WHERE source_file = ?", (src,))
        for chunk in chunks:
            conn.execute(
                "INSERT INTO faq_dataset (source_file, content_type, content, page_number, module, media_url, media_type, tenant_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (chunk["source_file"], chunk["content_type"], chunk["content"], chunk["page_number"], module, media_url, media_type, tenant_id),
            )


def save_knowledge_base_chunks(chunks, source_file, media_url=None, media_type=None, tenant_id=None, replace_existing=True):
    """Insert KB rows. Defaults to replace_existing so re-uploads do not leave
    stale FAISS/SQL duplicates for the same source + tenant.
    """
    grouped = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.get("source_file", source_file)].append(chunk)

    if use_mongodb():
        from .mongo import Repository
        repo = Repository("knowledge_base")
        for src, group in grouped.items():
            if replace_existing:
                filters = {"source": src}
                if tenant_id is not None:
                    filters["tenant_id"] = tenant_id
                repo.delete_many(filters)
            texts = [c.get("content", "") for c in group if c.get("content")]
            full_text = "\n".join(texts)
            repo.insert({
                "title": src,
                "category": "uploaded",
                "content": full_text,
                "tags": json.dumps([]),
                "source": src,
                "chunks_json": texts,
                "embedding_blob": None,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "media_url": media_url,
                "media_type": media_type,
                "tenant_id": tenant_id,
            })
        return

    with get_db_context() as conn:
        for src, group in grouped.items():
            if replace_existing:
                if tenant_id is not None:
                    conn.execute(
                        "DELETE FROM knowledge_base WHERE source = ? AND tenant_id = ?",
                        (src, tenant_id),
                    )
                else:
                    conn.execute("DELETE FROM knowledge_base WHERE source = ?", (src,))
            texts = [c.get("content", "") for c in group if c.get("content")]
            full_text = "\n".join(texts)
            conn.execute(
                """INSERT INTO knowledge_base (title, category, content, tags, source, chunks_json, embedding_blob, created_at, media_url, media_type, tenant_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    src,
                    "uploaded",
                    full_text,
                    json.dumps([]),
                    src,
                    json.dumps(texts),
                    None,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    media_url,
                    media_type,
                    tenant_id,
                ),
            )


def get_files_summary():
    if use_mongodb():
        from .mongo import get_database
        pipeline = [
            {"$group": {"_id": {"source_file": "$source_file", "module": "$module"}, "chunk_count": {"$sum": 1}}},
            {"$project": {
                "_id": 0,
                "source_file": "$_id.source_file",
                "module": "$_id.module",
                "chunk_count": 1,
            }},
            {"$sort": {"source_file": 1}},
        ]
        return list(get_database()["faq_dataset"].aggregate(pipeline))
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT source_file, module, COUNT(*) as chunk_count FROM faq_dataset GROUP BY source_file ORDER BY source_file"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_file_chunks(source_file, tenant_id=None):
    if use_mongodb():
        from .mongo import Repository
        filters = {"source_file": source_file}
        if tenant_id:
            filters["tenant_id"] = tenant_id
        return Repository("faq_dataset").delete_many(filters)
    with get_db_context() as conn:
        if tenant_id:
            result = conn.execute(
                "DELETE FROM faq_dataset WHERE source_file = ? AND tenant_id = ?",
                (source_file, tenant_id),
            )
        else:
            result = conn.execute("DELETE FROM faq_dataset WHERE source_file = ?", (source_file,))
        return result.rowcount


def delete_knowledge_base_file(source_file, tenant_id=None):
    if use_mongodb():
        from .mongo import Repository
        filters = {"source": source_file}
        if tenant_id:
            filters["tenant_id"] = tenant_id
        return Repository("knowledge_base").delete_many(filters)
    with get_db_context() as conn:
        if tenant_id:
            result = conn.execute(
                "DELETE FROM knowledge_base WHERE source = ? AND tenant_id = ?",
                (source_file, tenant_id),
            )
        else:
            result = conn.execute("DELETE FROM knowledge_base WHERE source = ?", (source_file,))
        return result.rowcount
