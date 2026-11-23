import os
import json
import base64
import logging
import uuid
import asyncio
from typing import List
from pathlib import Path
from fastapi import APIRouter, Body, UploadFile, File, HTTPException, Depends, Query, Request, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, Response
from pydantic import BaseModel
from database import (
    get_files_summary, delete_file_chunks, delete_knowledge_base_file, save_chunks, get_db, get_db_context,
    list_admin_files, list_products, get_products_by_category, save_admin_file, delete_admin_file,
    get_menu_items, upsert_menu_item, reset_menu, get_menu_settings, set_menu_settings,
    record_admin_audit_event, update_admin_file_status,
    save_product, update_product, delete_product,
    list_webhook_logs, clear_webhook_logs,
)
from db.admin_ops import (
    admin_chat_history,
    admin_list_customers,
    analytics_frequent_questions,
    analytics_overview,
    analytics_response_time,
    analytics_top_questions,
    analytics_unanswered,
    convert_unanswered_to_faq,
    dashboard_stats as load_dashboard_stats,
    delete_admin_file_row,
    get_admin_file_row,
)
from db.core import use_mongodb
from services.menu_catalog import (
    invalidate_menu_cache, get_menu_editor_items, get_effective_item,
)
from extract import process_file, results_to_chunks
from routes.auth import get_current_admin, has_permission, require_permission, require_super_admin, scoped_tenant_id
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger("chiki_webhook")
router = APIRouter(prefix="/api/admin")


def _record_audit(**kwargs):
    if use_mongodb():
        record_admin_audit_event(None, **kwargs)
    else:
        with get_db_context() as conn:
            record_admin_audit_event(conn, **kwargs)


def _tenant_clause(admin: dict, column: str, params: list) -> str:
    """AND-fragment that pins a query to the caller's tenant. Empty for super admins."""
    scope = scoped_tenant_id(admin)
    if not scope:
        return ""
    params.append(scope)
    return f" AND {column} = ?"

# D5: single source of truth — routing.config.UPLOAD_DIR honours the
# UPLOAD_DIR env var (external storage); the repo tree is only the default.
from routing.config import UPLOAD_DIR
SUPPORTED = (".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".md", ".csv")
#: Knowledge-base / FAQ uploads (the Uploads screen and the live inbox share it).
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _find_uploaded_file(filename: str) -> str | None:
    for root, _, files in os.walk(UPLOAD_DIR):
        if filename in files:
            return os.path.join(root, filename)
    return None


def _guess_media_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
    }.get(ext, "application/octet-stream")


# ── Dashboard stats (available to every authenticated admin) ─────────────

def _mongo_network_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return name in {
        "NetworkTimeout",
        "ServerSelectionTimeoutError",
        "AutoReconnect",
        "ConnectionFailure",
        "NetworkTimeoutError",
    } or "timed out" in text or "10054" in text or "forcibly closed" in text


def _reset_mongo_client() -> None:
    try:
        from db.mongo import close_client
        close_client()
    except Exception:
        logger.debug("mongo client reset skipped", exc_info=True)


@router.post("/dashboard/overview")
def dashboard_overview(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(8, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin),
):
    """Return every dashboard metric in one tenant-scoped response.

    Mongo network blips must not 500 the whole Today page — each section is
    isolated and missing pieces degrade to empty defaults.
    """
    tenant_id = scoped_tenant_id(current_admin)

    def _safe(label: str, fn, default):
        try:
            return fn()
        except Exception as exc:
            if _mongo_network_error(exc):
                _reset_mongo_client()
            logger.warning("DASHBOARD_SECTION_FAILED | section=%s | err=%s", label, exc)
            return default

    files = _safe(
        "files",
        lambda: list_admin_files(tenant_id=tenant_id) if tenant_id else list_admin_files(),
        [],
    )
    kb_count = len([f for f in files if f.get("module") == "kb"])
    faq_count = len([f for f in files if f.get("module") == "faq"])

    def _product_count() -> int:
        if tenant_id:
            if use_mongodb():
                from db.mongo import Repository
                return Repository("products").count(
                    {"tenant_id": tenant_id, "is_active": 1}
                )
            return len(list_products(limit=10000, tenant_id=tenant_id))
        if use_mongodb():
            from db.mongo import Repository
            return Repository("products").count({"is_active": 1})
        with get_db_context() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM products WHERE is_active = 1"
            ).fetchone()["c"]

    product_count = _safe("products", _product_count, 0)

    empty_stats = {
        "kb_files": kb_count,
        "faq_files": faq_count,
        "products": product_count,
        "top_questions": [],
        "total_customers": 0,
        "total_orders": 0,
        "orders_solved": 0,
        "total_complaints": 0,
        "complaints_solved": 0,
    }
    stats = _safe(
        "stats",
        lambda: load_dashboard_stats(
            kb_count=kb_count,
            faq_count=faq_count,
            product_count=product_count,
            tenant_id=tenant_id,
        ),
        empty_stats,
    )
    overview = _safe(
        "overview",
        lambda: analytics_overview(days=days, tenant_id=tenant_id),
        {
            "days": days,
            "total_messages": 0,
            "unique_users": 0,
            "avg_response_ms": 0,
            "route_breakdown": [],
        },
    )
    response_time = _safe(
        "response_time",
        lambda: analytics_response_time(days=days, tenant_id=tenant_id),
        {"days": days, "data": []},
    )
    questions = _safe(
        "frequent_questions",
        lambda: analytics_frequent_questions(days=days, limit=limit, tenant_id=tenant_id),
        {"days": days, "total_unique": 0, "questions": []},
    )
    return {
        **stats,
        **overview,
        "response_time": response_time["data"],
        "frequent_questions": questions["questions"],
        "total_unique_questions": questions["total_unique"],
    }


# ── Customers (aggregated from orders / complaints / chat_history) ────────

@router.get("/customers")
def list_customers(
    q: str = Query("", max_length=100),
    limit: int = Query(200, le=1000),
    current_admin: dict = Depends(require_permission("view_customers")),
):
    """List customers aggregated across orders, complaints and chat history.

    Each customer is identified by their WhatsApp ID (wa_id). The endpoint
    returns their best-known name/mobile, order and complaint totals, total
    spend, and last activity timestamp.
    """
    return admin_list_customers(q=q, limit=limit)


@router.get("/logs")
def get_logs(
    direction: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_admin: dict = Depends(require_super_admin),
):
    return list_webhook_logs(limit=limit, direction=direction)


@router.delete("/logs")
def clear_logs(current_admin: dict = Depends(require_super_admin)):
    clear_webhook_logs()
    return {"status": "ok", "message": "Logs cleared"}


# ── Rebuild FAISS index + generate missing embeddings (no restart needed) ─

@router.post("/rebuild-index")
async def rebuild_index(background_tasks: bool = Query(False), payload: dict | None = Body(None), current_admin: dict = Depends(get_current_admin)):
    """
    Rebuild all FAISS indexes and generate any missing embeddings.
    Runs in background by default so the endpoint returns immediately.
    Pass ?background_tasks=false to run synchronously (slower response).

    The rebuild itself is global (a platform power). A super admin is
    view-only inside tenants, so a TENANT-SCOPED rebuild request (a body
    carrying tenant_id) from a super admin is refused (QA D-21, 2026-11-13);
    the global rebuild stays available to them.
    """
    requested_tenant = str((payload or {}).get("tenant_id") or "").strip()
    if requested_tenant and current_admin.get("role") == "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Super admins are view-only inside tenants and cannot rebuild a tenant's index",
        )
    def _do_rebuild():
        results = {}

        # 1. Rebuild KB chunks + missing embeddings + FAISS
        try:
            from kb.services.rag import build_chunks_for_kb, rebuild_faiss_index, generate_missing_embeddings
            build_chunks_for_kb()
            results["kb_chunks"] = "ok"
        except Exception as e:
            logger.error(f"KB build_chunks_for_kb failed: {e}")
            results["kb_chunks"] = f"error: {e}"

        try:
            from kb.services.rag import generate_missing_embeddings
            generate_missing_embeddings()
            results["kb_embeddings"] = "ok"
        except Exception as e:
            logger.error(f"KB generate_missing_embeddings failed: {e}")
            results["kb_embeddings"] = f"error: {e}"

        try:
            from kb.services.rag import rebuild_faiss_index
            rebuild_faiss_index()
            results["kb_faiss"] = "ok"
        except Exception as e:
            logger.error(f"KB rebuild_faiss_index failed: {e}")
            results["kb_faiss"] = f"error: {e}"

        # 2. Rebuild FAQ index (hybrid dense+sparse+reranker)
        try:
            from faq.service import faq_index
            faq_index.build(force=True)
            results["faq_index"] = "ok"
            results["faq_vectors"] = faq_index.index.ntotal if faq_index.is_built else 0
        except Exception as e:
            logger.error(f"FAQ index build failed: {e}")
            results["faq_index"] = f"error: {e}"

        # 3. Rebuild product FAISS index
        try:
            from kb.services.rag import rebuild_product_faiss_index
            rebuild_product_faiss_index()
            results["product_index"] = "ok"
        except Exception as e:
            logger.error(f"Product index build failed: {e}")
            results["product_index"] = f"error: {e}"

        return results

    if background_tasks:
        import threading
        threading.Thread(target=_do_rebuild, daemon=True).start()
        return {"status": "rebuild_started", "detail": "Index rebuild running in background. Check logs for completion."}
    else:
        results = await run_in_threadpool(_do_rebuild)
        return {"status": "ok", "results": results}


# ── Analytics endpoints ───────────────────────────────────────────────────

# ── Top questions ─────────────────────────────────────────────────────────

@router.get("/analytics/top-questions")
def get_top_questions(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    current_admin: dict = Depends(get_current_admin),
):
    return analytics_top_questions(
        days=days, limit=limit, tenant_id=scoped_tenant_id(current_admin),
    )


class UnansweredToFAQ(BaseModel):
    query: str
    answer: str
    tenant_id: str = "default"
    module: str = "faq"


@router.post("/analytics/unanswered/convert")
def convert_unanswered_to_faq(
    body: UnansweredToFAQ,
    current_admin: dict = Depends(require_permission("upload_faq")),
):
    """Turn a repeatedly-unanswered question into an FAQ the bot can answer.

    Writes a tenant-tagged faq_dataset row; the embedding is generated on the
    next FAQ index build (missing embeddings are computed there), so this
    insert needs no model in the request path.
    """
    query = body.query.strip()
    answer = body.answer.strip()
    if not query or not answer:
        raise HTTPException(status_code=400, detail="Both query and answer are required")
    scope = scoped_tenant_id(current_admin)
    target_tenant = (body.tenant_id or "").strip() or "default"
    if scope and target_tenant != scope:
        raise HTTPException(status_code=403, detail=f"Admin is scoped to tenant '{scope}'")

    row_id = convert_unanswered_to_faq(
        query=query,
        answer=answer,
        module=body.module.strip() or "faq",
        tenant_id=target_tenant,
        source_file=f"admin_unanswered_{current_admin.get('username', 'admin')}",
    )
    logger.info(
        "UNANSWERED_CONVERTED_TO_FAQ | admin=%s | tenant=%s | faq_id=%s",
        current_admin.get("username"), body.tenant_id, row_id)
    return {
        "ok": True,
        "faq_id": row_id,
        "tenant_id": body.tenant_id,
        "note": "Rebuild the FAQ index (Knowledge Base -> Rebuild) to make this answer live.",
    }


# ── Unanswered queries ────────────────────────────────────────────────────

@router.get("/analytics/unanswered")
def get_unanswered_queries(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin),
):
    return analytics_unanswered(
        days=days, limit=limit, tenant_id=scoped_tenant_id(current_admin),
    )


# ── File management ───────────────────────────────────────────────────────

@router.get("/files")
def list_admin_files_api(
    module: str = Query(None),
    search: str = Query(None),
    current_admin: dict = Depends(require_permission("view_files")),
):
    files = list_admin_files()
    if module:
        files = [f for f in files if f.get("module") == module]
    if search:
        s = search.lower()
        files = [f for f in files if s in f.get("name", "").lower()]
    return {"files": files}


@router.get("/files/{filename}/preview")
def preview_admin_file(
    filename: str,
    current_admin: dict = Depends(require_permission("view_files")),
):
    filepath = _find_uploaded_file(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="File not found")
    media_type = _guess_media_type(filename)
    return FileResponse(filepath, media_type=media_type, headers={"Content-Disposition": f"inline; filename=\"{filename}\""})


@router.get("/files/{filename}/download")
def download_admin_file(
    filename: str,
    current_admin: dict = Depends(require_permission("view_files")),
):
    filepath = _find_uploaded_file(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="File not found")
    media_type = _guess_media_type(filename)
    return FileResponse(filepath, filename=filename, media_type=media_type, headers={"Content-Disposition": f"attachment; filename=\"{filename}\""})


@router.get("/download-remote")
def download_remote_file(
    url: str = Query(...),
    filename: str = Query(None),
    current_admin: dict = Depends(require_permission("view_files")),
):
    """Proxy-download an arbitrary remote file (e.g. catbox/image hosts) so the
    browser always receives Content-Disposition: attachment, avoiding CORS and
    MIME issues that break direct cross-origin downloads."""
    import httpx
    import mimetypes

    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")
    name = filename or url.split("/")[-1].split("?")[0] or "download"
    try:
        with httpx.Client(trust_env=False, follow_redirects=True, timeout=60) as client:
            resp = client.get(url)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"download-remote failed for {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch remote file: {e}")
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(
        content=resp.content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=\"{name}\""},
    )


@router.delete("/files/{filename}")
def delete_admin_file_api(
    filename: str,
    current_admin: dict = Depends(require_permission("delete_files")),
):
    filepath = _find_uploaded_file(filename)
    if not filepath:
        raise HTTPException(status_code=404, detail="File not found on disk")
    deleted_faq = delete_file_chunks(filename)
    deleted_kb = delete_knowledge_base_file(filename)
    delete_admin_file(filename, actor=current_admin)
    try:
        os.remove(filepath)
    except OSError:
        # deliberate: the DB records are already deleted; a file that
        # cannot be removed (already gone/locked) is only logged.
        logger.debug("FILE_DELETE_CLEANUP_SKIPPED | path=%s", filepath, exc_info=True)
    logger.info(f"Deleted: {filename} (faq={deleted_faq}, kb={deleted_kb})")
    return {"status": "ok", "filename": filename, "deleted_faq": deleted_faq, "deleted_kb": deleted_kb}


@router.post("/files/upload")
async def upload_admin_file(
    request: Request,
    background_tasks: BackgroundTasks,
    module: str = Query("faq"),
    url: str = Query(None),
    media_type: str = Query(None),
    current_admin: dict = Depends(get_current_admin),
):
    """Upload a FAQ/KB/catalogue file (single-tenant path).

    The tenant-aware variant lives in ``routes/tenant_files.py``; both share
    ``run_upload`` so the extraction/indexing logic exists once.
    """
    return await run_upload(request, module, url, media_type, current_admin, tenant_id=None, background_tasks=background_tasks)


def _process_document_background(
    filepath: str,
    filename: str,
    ext: str,
    module: str,
    effective_url: str,
    effective_media_type: str,
    tenant_id: str | None,
):
    """Background worker for document text extraction, chunking, and vector index builds.

    After chunk indexing, runs full LLM auto-bifurcation (products / FAQ / KB / careful
    brand merge) when AUTO_BIFURCATE_FULL is enabled (default on).
    """
    chunks = []
    bifurcation_stats = None
    try:
        # Drop prior indexed rows for this file so re-uploads do not duplicate.
        try:
            delete_file_chunks(filename, tenant_id=tenant_id)
            delete_knowledge_base_file(filename, tenant_id=tenant_id)
        except Exception as purge_err:
            logger.warning("Pre-ingest purge failed for %s: %s", filename, purge_err)

        results = process_file(filepath)
        if results:
            chunks = results_to_chunks(results)
            if chunks:
                if module == "kb":
                    from database import save_knowledge_base_chunks
                    save_knowledge_base_chunks(
                        chunks,
                        filename,
                        media_url=effective_url,
                        media_type=effective_media_type,
                        tenant_id=tenant_id,
                        replace_existing=True,
                    )
                    try:
                        from kb.services.rag import build_chunks_for_kb, generate_missing_embeddings, rebuild_faiss_index
                        build_chunks_for_kb()
                        generate_missing_embeddings()
                        rebuild_faiss_index()
                        logger.info(f"KB_FAISS_REBUILT | {filename} ({len(chunks)} chunks)")
                    except Exception as e:
                        logger.error(f"KB FAISS rebuild failed after background upload {filename}: {e}")
                else:
                    save_chunks(
                        chunks,
                        module=module,
                        media_url=effective_url,
                        media_type=effective_media_type,
                        tenant_id=tenant_id,
                        replace_existing=True,
                    )
                try:
                    from faq.service import faq_index
                    faq_index.build(force=True)
                    logger.info(f"FAQ_INDEX_AUTOSYNCED | {filename} ({len(chunks)} chunks)")
                except Exception as e:
                    logger.warning(f"FAQ index auto-sync failed after background upload {filename}: {e}")

                # Legacy tenant_kb/tenant_faq writer is OFF by default — those tables
                # are not used by live retrieval (faq_dataset / knowledge_base are).
                # Opt in with AUTO_BIFURCATE=1 only when you still need that path.
                if os.environ.get("AUTO_BIFURCATE", "0").strip().lower() not in ("0", "false", "no", "off"):
                    try:
                        try:
                            from bifurcate import bifurcate_and_save_chunks
                        except ImportError:
                            from backend.bifurcate import bifurcate_and_save_chunks
                        target_tenant = tenant_id or os.environ.get("DEFAULT_TENANT_ID") or "default"
                        split = bifurcate_and_save_chunks(
                            chunks,
                            target_tenant,
                            use_llm=os.environ.get("BIFURCATE_USE_LLM", "1").strip().lower()
                            not in ("0", "false", "no", "off"),
                        )
                        logger.info(
                            "AUTO_BIFURCATION_COMPLETED | %s | tenant=%s | industry=%s | kb=%d faq=%d",
                            filename, target_tenant, split["industry"], split["kb_chunks"], split["faq_chunks"],
                        )
                    except Exception as e:
                        logger.warning(f"Auto-bifurcation failed after background upload {filename}: {e}")

        # Full semantic route: products (live) + FAQs + KB + careful brand/menu merge
        if tenant_id and os.path.exists(filepath):
            try:
                with open(filepath, "rb") as disk_f:
                    raw_bytes = disk_f.read()
                try:
                    from services.upload_auto_router import route_uploaded_document
                except ImportError:
                    from backend.services.upload_auto_router import route_uploaded_document
                bifurcation_stats = route_uploaded_document(
                    tenant_id=tenant_id,
                    filename=filename,
                    content=raw_bytes,
                    actor={"username": "upload_auto_router", "role": "system", "tenant_id": tenant_id},
                )
            except Exception as e:
                logger.warning(f"Full upload auto-router failed for {filename}: {e}", exc_info=True)
                bifurcation_stats = {"status": "error", "error": str(e), "files_processed": [filename]}

        bif_err = (
            isinstance(bifurcation_stats, dict)
            and str(bifurcation_stats.get("status") or "").lower() == "error"
        )
        # Only DOCUMENT-DERIVED bifurcation output counts as useful. The
        # auto-router can also emit template menu buttons / intents from
        # vertical defaults for a document it could not read at all, and
        # counting those let a corrupt upload end 'ready' with 0 chunks and
        # an empty error message (QA 2026-11-13).
        bif_useful = isinstance(bifurcation_stats, dict) and any(
            int(bifurcation_stats.get(k) or 0)
            for k in ("offerings_created", "faqs_saved", "kb_chunks_indexed")
        )
        # Extraction yield: the extractors return a result dict even for a
        # file they could not parse (a corrupt PDF yields empty
        # pages/tables/images). No pages, paragraphs, tables or rows at all
        # means the file itself could not be read.
        parse_failed = not results or not any(
            results.get(k) for k in ("pages", "paragraphs", "tables", "rows", "text")
        )
        # Brochure modules may be deliverable as the file itself (0 chunks OK
        # when the file parsed). FAQ/KB uploads with no extract and no useful
        # bifurcation are failures — and so is any upload whose file could
        # not be parsed at all.
        no_content = len(chunks) == 0 and not bif_useful and (
            bif_err or parse_failed or module in ("faq", "kb")
        )
        if no_content:
            err_msg = None
            if isinstance(bifurcation_stats, dict):
                err_msg = bifurcation_stats.get("error")
            if not err_msg and parse_failed:
                err_msg = (
                    "The file could not be parsed — it may be corrupt, "
                    "password-protected, or in an unsupported format. "
                    "No content could be extracted from it."
                )
            update_admin_file_status(
                filename,
                status="failed",
                chunks_count=0,
                error_message=err_msg or "No text could be extracted or configured from the document",
                tenant_id=tenant_id,
                bifurcation_stats=bifurcation_stats,
            )
            logger.warning(
                "ASYNC_INGESTION_EMPTY | %s | chunks=0 | bif_err=%s | tenant=%s",
                filename, bif_err, tenant_id,
            )
        else:
            update_admin_file_status(
                filename,
                status="ready",
                chunks_count=len(chunks),
                error_message="",
                tenant_id=tenant_id,
                bifurcation_stats=bifurcation_stats,
            )
            logger.info(f"ASYNC_INGESTION_COMPLETED | {filename} | chunks={len(chunks)} | tenant={tenant_id}")
            try:
                from kb.services.brain import clear_response_cache
                clear_response_cache()
            except Exception:
                logger.exception("RESPONSE_CACHE_CLEAR_FAILED | file=%s", filename)

            # Auto-split onboarding/main PDFs into FAQ + KB derivative files.
            if ext.lower() == ".pdf" and os.path.exists(filepath):
                try:
                    from services.pdf_section_extractor import auto_extract_and_register
                    extraction_result = auto_extract_and_register(
                        source_filepath=filepath,
                        original_filename=filename,
                        tenant_id=tenant_id,
                        # Upload polling tracks this exact filename and module.
                        # Keep its ready row and stats when derivatives are added.
                        cleanup_original=False,
                        actor={
                            "username": "auto_extractor",
                            "role": "system",
                            "tenant_id": tenant_id,
                        },
                    )
                    logger.info(
                        "PDF_SECTION_EXTRACTION | %s | faq=%s | kb=%s",
                        filename,
                        extraction_result.get("faq_pdf"),
                        extraction_result.get("kb_pdf"),
                    )
                except Exception as _ext_err:
                    logger.warning(
                        "PDF section extraction failed for %s: %s", filename, _ext_err
                    )
    except Exception as exc:
        logger.error(f"ASYNC_INGESTION_FAILED | {filename}: {exc}", exc_info=True)
        update_admin_file_status(
            filename,
            status="failed",
            error_message=str(exc),
            tenant_id=tenant_id,
            bifurcation_stats=bifurcation_stats,
        )


async def run_upload(
    request: Request,
    module: str,
    url: str | None,
    media_type: str | None,
    current_admin: dict,
    tenant_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
):
    if module == "kb":
        if not has_permission(current_admin, "upload_kb"):
            raise HTTPException(status_code=403, detail="You do not have permission to upload KB files")
    else:
        if not has_permission(current_admin, "upload_faq"):
            raise HTTPException(status_code=403, detail="You do not have permission to upload FAQ files")
    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    content_type = request.headers.get("content-type", "")
    filename = ""
    content = b""
    is_image = False

    if "application/json" in content_type:
        body = await request.json()
        filename = body.get("filename", "")
        raw_b64 = body.get("content", "") or ""
        if isinstance(raw_b64, str) and raw_b64.startswith("data:") and "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            content = base64.b64decode(raw_b64, validate=False)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid Base64 in 'content'. Encode the real file bytes "
                    "(not the placeholder BASE64_FILE_CONTENT). "
                    f"Decoder said: {exc}"
                ),
            ) from exc
        if not content:
            raise HTTPException(
                status_code=400,
                detail="Decoded file content is empty — check the Base64 payload.",
            )
        if not url:
            url = body.get("url")
        if not media_type:
            media_type = body.get("media_type")
    elif "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload and hasattr(upload, "read"):
            filename = upload.filename or "unknown"
            content = await upload.read()
            if hasattr(upload, "content_type") and upload.content_type and upload.content_type.startswith("image/"):
                is_image = True
        url = form.get("url") or url
        media_type = form.get("media_type") or media_type
    else:
        raise HTTPException(status_code=400, detail="Unsupported content type")

    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Files must be under {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    ext = Path(filename).suffix.lower()
    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
    if ext in image_exts or is_image:
        # Store images on this backend and return its configured public URL.
        try:
            from services.media_host import upload_public_image
        except ImportError:
            from backend.services.media_host import upload_public_image
        effective_url = await run_in_threadpool(
            upload_public_image, content, filename or "image.png", media_type or ""
        )
        if not effective_url:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Image upload failed. Configure PUBLIC_BASE_URL and verify UPLOAD_DIR."
                ),
            )
        effective_media_type = media_type or ext.lstrip(".")
        save_admin_file(
            filename,
            ext.lstrip("."),
            module,
            len(content),
            url=effective_url,
            tenant_id=tenant_id,
            actor=current_admin,
        )
        return {
            "status": "ok",
            "filename": filename,
            "module": module,
            "chunks": 0,
            "size": len(content),
            "file_url": effective_url,
        }

    if ext not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Store on disk and expose PDFs through PUBLIC_BASE_URL. Catalogue PDF text is intentionally
    # NOT imported into products — "catalogue" requests send the PDF.
    module_dir = os.path.join(UPLOAD_DIR, module)
    os.makedirs(module_dir, exist_ok=True)
    filepath = os.path.join(module_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    size = len(content)

    local_rel = f"/uploaded_files/{module}/{filename}"
    tunnel_url = None
    if not url:
        try:
            from services.media_host import absolutize_upload_url
        except ImportError:
            from backend.services.media_host import absolutize_upload_url
        tunnel_url = absolutize_upload_url(local_rel)
        if tunnel_url and tunnel_url != local_rel:
            logger.info(f"PDF_PUBLIC_BASE | {filename} -> {tunnel_url}")

    effective_url = url or tunnel_url or local_rel
    effective_media_type = media_type or ext.lstrip(".")

    save_admin_file(
        filename,
        ext.lstrip("."),
        module,
        size,
        file_path=filepath,
        url=effective_url,
        tenant_id=tenant_id,
        actor=current_admin,
        status="processing",
        chunks_count=0,
    )

    if background_tasks:
        background_tasks.add_task(
            _process_document_background,
            filepath,
            filename,
            ext,
            module,
            effective_url,
            effective_media_type,
            tenant_id,
        )
    else:
        asyncio.create_task(
            run_in_threadpool(
                _process_document_background,
                filepath,
                filename,
                ext,
                module,
                effective_url,
                effective_media_type,
                tenant_id,
            )
        )

    logger.info(f"ASYNC_INGESTION_DISPATCHED | {filename} ({size} bytes) | tenant={tenant_id}")
    return {
        "status": "ok",
        "state": "processing",
        "filename": filename,
        "module": module,
        "chunks": 0,
        "size": size,
        "file_url": effective_url,
        "message": f"Document '{filename}' uploaded successfully. Vector chunking and index builds are processing in the background.",
    }


# ── Chat history with user lookup ─────────────────────────────────────────

@router.get("/chat-history")
def get_chat_history_api(
    days: int = Query(30, ge=1, le=1095),
    from_date: str = Query(None),
    to_date: str = Query(None),
    search: str = Query(None),
    current_admin: dict = Depends(require_permission("chat_history")),
):
    return admin_chat_history(
        days=days,
        from_date=from_date,
        to_date=to_date,
        search=search,
        tenant_id=scoped_tenant_id(current_admin),
    )


# ── Products / Catalogue ──────────────────────────────────────────────────

@router.get("/products")
def list_products_api(
    category: str = Query(None),
    search: str = Query(None),
    current_admin: dict = Depends(require_permission("view_products")),
):
    products = list_products(category=category, active_only=False)
    if search:
        s = search.lower()
        products = [p for p in products if s in p.get("name", "").lower() or s in p.get("description", "").lower()]
    return {"products": products}


@router.post("/products")
def create_product_api(
    data: dict,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    name = data.get("name", "")
    slug = data.get("slug", "")
    if not name or not slug:
        raise HTTPException(status_code=400, detail="name and slug are required")
    pid = save_product(
        name=name,
        slug=slug,
        category=data.get("category", "general"),
        description=data.get("description", ""),
        short_description=data.get("short_description", ""),
        price=data.get("price", ""),
        mrp=data.get("mrp", ""),
        unit=data.get("unit", "piece"),
        moq=data.get("moq", ""),
        media_url=data.get("media_url"),
        media_type=data.get("media_type", "image"),
        ingredients=data.get("ingredients", []),
        sort_order=data.get("sort_order", 0),
        stock_quantity=data.get("stock_quantity"),
        nutritional_facts=data.get("nutritional_facts"),
        bulk_discount_tiers=data.get("bulk_discount_tiers", []),
        actor=current_admin,
    )
    return {"status": "ok", "id": pid}


@router.put("/products/{product_id}")
def update_product_api(
    product_id: int,
    data: dict,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    allowed = {k: v for k, v in data.items() if k in {
        "name", "slug", "category", "description", "short_description",
        "price", "mrp", "unit", "moq", "media_url", "media_type", "ingredients", "is_active", "sort_order",
        "stock_quantity", "nutritional_facts", "bulk_discount_tiers"
    }}
    if "ingredients" in allowed and isinstance(allowed["ingredients"], list):
        allowed["ingredients"] = json.dumps(allowed["ingredients"])
    if "bulk_discount_tiers" in allowed and isinstance(allowed["bulk_discount_tiers"], list):
        allowed["bulk_discount_tiers"] = json.dumps(allowed["bulk_discount_tiers"])
    ok = update_product(product_id, actor=current_admin, **allowed)
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"status": "ok"}


@router.delete("/products/{product_id}")
def delete_product_api(
    product_id: int,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    ok = delete_product(product_id, hard=True, actor=current_admin)
    if not ok:
        raise HTTPException(status_code=400, detail="Delete failed")
    return {"status": "ok"}


async def _upload_to_catbox(filename: str, content: bytes, content_type: str = "application/octet-stream") -> str:
    """Legacy helper name: store bytes on this backend, never on Catbox."""
    try:
        from services.media_host import upload_public_media
    except ImportError:
        from backend.services.media_host import upload_public_media
    subdir = "product_images" if content_type.startswith("image/") else "brochures"
    url = await run_in_threadpool(upload_public_media, content, filename, content_type, subdir=subdir)
    if not url:
        raise HTTPException(status_code=503, detail="Local media hosting is not configured")
    return url


@router.post("/upload/image")
async def upload_public_image_file(
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The file is empty")
    try:
        from services.media_host import upload_public_image
    except ImportError:
        from backend.services.media_host import upload_public_image
    url = await run_in_threadpool(
        upload_public_image,
        contents,
        file.filename or "image.png",
        file.content_type,
    )
    if not url:
        raise HTTPException(status_code=503, detail="Public image hosting is not configured")
    return {"url": url, "media_type": file.content_type}


LOGOS_DIR = os.path.join(UPLOAD_DIR, "logos")
os.makedirs(LOGOS_DIR, exist_ok=True)
MAX_LOGO_BYTES = 5 * 1024 * 1024


@router.post("/upload/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Store a company logo on disk and return a URL the console can render.

    Kept local (served at ``/api/logos/...``) so it needs no third-party host or
    API key; the profile stores the returned URL as ``brand.logo_url``. PNG only.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".png" or not (file.content_type or "").startswith("image/png"):
        raise HTTPException(status_code=400, detail="The logo must be a PNG image")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(contents) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="The logo must be under 5 MB")

    name = f"{uuid.uuid4().hex}.png"
    with open(os.path.join(LOGOS_DIR, name), "wb") as handle:
        handle.write(contents)
    return {"url": f"/api/logos/{name}", "media_type": "image/png"}

@router.post("/upload/catbox")
async def upload_to_catbox(file: UploadFile = File(...)):
    """Backward-compatible endpoint that now stores files on this backend."""
    contents = await file.read()
    url = await _upload_to_catbox(
        file.filename or "file",
        contents,
        file.content_type or "application/octet-stream",
    )
    return {"url": url, "media_type": file.content_type or "application/octet-stream"}


#: Chat attachments (admin chat + live inbox) are stored on our own disk under
#: ``uploaded_files/chat_attachments`` and served at ``/api/uploads/chat/...``
#: (mounted in main.py) so no third-party host or API key is involved. Kept
#: small enough not to hold a request open for minutes.
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
CHAT_ATTACHMENTS_DIR = os.path.join(UPLOAD_DIR, "chat_attachments")
os.makedirs(CHAT_ATTACHMENTS_DIR, exist_ok=True)


def decode_attachment_body(data: dict) -> tuple[str, bytes, str | None]:
    """Validate a base64 JSON attachment body into ``(filename, bytes, type)``."""
    filename = (data.get("filename") or "").strip()
    raw = data.get("content") or ""
    if not filename or not raw:
        raise HTTPException(status_code=400, detail="filename and content are required")
    try:
        content = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="content must be base64")
    if not content:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Attachments must be under {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB",
        )
    return filename, content, data.get("media_type")


async def store_chat_attachment(filename: str, content: bytes, media_type: str | None = None) -> dict:
    """Save a chat/inbox attachment and return a public WhatsApp-ready URL.

    Images and documents are always served directly from this backend.
    """
    ext = Path(filename).suffix.lower()
    is_image = (media_type or "").startswith("image/") or ext in _IMAGE_EXTS
    safe_ext = ext if 0 < len(ext) <= 10 else (".png" if is_image else ".bin")
    stored = f"{uuid.uuid4().hex}{safe_ext}"
    local_path = os.path.join(CHAT_ATTACHMENTS_DIR, stored)
    with open(local_path, "wb") as handle:
        handle.write(content)

    local_url = f"/api/uploads/chat/{stored}"
    from routing.config import PUBLIC_BASE_URL
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    public_url = f"{base}{local_url}" if base else local_url

    logger.info("CHAT_ATTACH_LOCAL | %s -> %s", filename, public_url)

    return {
        "url": public_url,
        "local_url": local_url,
        "name": filename,
        "type": "image" if is_image else "document",
        "size": len(content),
        "media_type": media_type or ("image/*" if is_image else "application/octet-stream"),
    }


# ── Menu Editor (admin-editable WhatsApp menus) ──────────────────────────
#
# HOW IT WORKS NOW (the "toggling one item kills the whole menu" fix):
# The `menus` table stores PER-ITEM OVERRIDES on top of the hard-coded
# defaults in services/menu_catalog.py — it is never a replacement for the
# whole menu. GET endpoints therefore ALWAYS return the full merged list
# (every default item + admin-created items, with override values applied),
# so the editor keeps showing all items no matter how many have been edited.
# A single PUT toggling is_active now hides exactly that one item at runtime.

KNOWN_MENU_KEYS = ["kb_main"]


@router.post("/menus")
def list_menus_api(current_admin: dict = Depends(get_current_admin)):
    """All menu keys with their full merged item lists (defaults + overrides)."""
    return {
        "menus": [
            {"menu_key": key, "items": get_menu_editor_items(key)}
            for key in KNOWN_MENU_KEYS
        ]
    }


# NOTE: nested settings / items / reorder / reset / update / delete routes
# are declared before the bare POST /menus/{menu_key} so path segments like
# "settings" are never captured as a menu_key or item_id.
@router.post("/menus/{menu_key}/settings")
def get_menu_settings_api(menu_key: str, current_admin: dict = Depends(get_current_admin)):
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")
    return {"menu_key": menu_key, "settings": get_menu_settings(menu_key)}


@router.post("/menus/{menu_key}/settings/update")
def set_menu_settings_api(
    menu_key: str,
    data: dict,
    request: Request,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")
    before = get_menu_settings(menu_key)
    if not set_menu_settings(menu_key, **data):
        raise HTTPException(status_code=400, detail="No valid settings fields supplied")
    after = get_menu_settings(menu_key)
    changed = {key: {"before": before.get(key), "after": after.get(key)} for key in data if before.get(key) != after.get(key)}
    _record_audit(action="menu_settings_updated", actor=current_admin, resource_type="menu", resource_id=menu_key, details={"changed_fields": sorted(changed), "changes": changed})
    invalidate_menu_cache()
    return {"ok": True, "menu_key": menu_key, "settings": after}


@router.post("/menus/{menu_key}/{item_id}/update")
def update_menu_item_api(
    menu_key: str,
    item_id: str,
    data: dict,
    request: Request,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    """Edit any field of a menu item, including item_id.

    Only the supplied fields are changed; everything else keeps its current
    effective value (DB override or code default). This is the fix for
    "can't edit menu items": a toggle of is_active no longer wipes the
    item's other fields, and editing/renaming an item that has never been
    saved to the DB works too (it used to 404 for renames).
    """
    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")

    # ── item_id rename ──────────────────────────────────────────────────
    new_item_id = data.get("item_id")
    if new_item_id and new_item_id != item_id:
        new_item_id = str(new_item_id).strip()
        if not new_item_id:
            raise HTTPException(status_code=400, detail="item_id cannot be empty")
        if get_effective_item(menu_key, new_item_id):
            raise HTTPException(status_code=400, detail=f"item_id '{new_item_id}' already exists")

        # BUG FIX: resolve the CURRENT item through the merged view so
        # renaming a never-edited (code-default) item works instead of 404.
        effective = get_effective_item(menu_key, item_id)
        if not effective:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

        # Merge incoming fields over the effective (DB-over-default) values
        merged = {
            "title": data.get("title", effective["title"]),
            "description": data.get("description", effective["description"]),
            "section": data.get("section", effective["section"]),
            "icon": data.get("icon", effective["icon"]),
            "sort_order": data.get("sort_order", effective["sort_order"]),
            "is_active": data.get("is_active", bool(effective["is_active"])),
        }

        # Delete old override row (if any), upsert the full item under the new key.
        # If the old id is a hard-coded code default, hide it with an inactive
        # override row — with per-item merge semantics the default would
        # otherwise keep reappearing alongside the renamed copy.
        try:
            from database import delete_menu_item
        except Exception:
            def delete_menu_item(mkey, iid):
                with get_db_context() as conn:
                    cur = conn.execute(
                        "DELETE FROM menus WHERE menu_key=? AND item_id=?", (mkey, iid)
                    )
                return cur.rowcount > 0

        delete_menu_item(menu_key, item_id)
        if effective["is_default"]:
            upsert_menu_item(menu_key, item_id, is_active=False)
        upsert_menu_item(menu_key, new_item_id, **merged)
        _record_audit(action="menu_item_updated", actor=current_admin, resource_type="menu_item", resource_id=f"{menu_key}/{new_item_id}", details={"menu_key": menu_key, "item_id": new_item_id, "renamed_from": item_id, "changed_fields": ["item_id", "title", "description", "section", "icon", "sort_order", "is_active"]})
        invalidate_menu_cache()
        return {"ok": True, "menu_key": menu_key, "item_id": new_item_id, "renamed_from": item_id}

    # ── normal field update (partial — unprovided fields are preserved) ──
    allowed = {"title", "description", "section", "icon", "sort_order", "is_active"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        raise HTTPException(status_code=400, detail="No editable fields supplied")
    effective = get_effective_item(menu_key, item_id)
    if not effective:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    changed = {key: {"before": effective.get(key), "after": value} for key, value in fields.items() if effective.get(key) != value}
    upsert_menu_item(menu_key, item_id, **fields)
    if changed:
        _record_audit(action="menu_item_updated", actor=current_admin, resource_type="menu_item", resource_id=f"{menu_key}/{item_id}", details={"menu_key": menu_key, "item_id": item_id, "changed_fields": sorted(changed), "changes": changed})
    invalidate_menu_cache()
    return {"ok": True, "menu_key": menu_key, "item_id": item_id}


@router.post("/menus/{menu_key}/items")
def create_menu_item_api(
    menu_key: str,
    data: dict,
    request: Request,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    """Add a brand-new item to the menu (stored as a DB row; it is not part
    of the code defaults, so Reset removes it)."""
    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")

    item_id = str(data.get("item_id", "")).strip()
    title = str(data.get("title", "")).strip()
    if not item_id or not title:
        raise HTTPException(status_code=400, detail="item_id and title are required")
    if get_effective_item(menu_key, item_id):
        raise HTTPException(status_code=400, detail=f"item_id '{item_id}' already exists")

    ok = upsert_menu_item(
        menu_key,
        item_id,
        title=title,
        description=data.get("description", ""),
        section=data.get("section", "General"),
        icon=data.get("icon", ""),
        sort_order=data.get("sort_order"),
        is_active=bool(data.get("is_active", True)),
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not create menu item")
    _record_audit(action="menu_item_created", actor=current_admin, resource_type="menu_item", resource_id=f"{menu_key}/{item_id}", details={"menu_key": menu_key, "item_id": item_id, "title": title[:120], "section": str(data.get("section", "General"))[:80]})
    invalidate_menu_cache()
    return {"ok": True, "menu_key": menu_key, "item_id": item_id}


@router.post("/menus/{menu_key}/reorder")
def reorder_menu_items_api(
    menu_key: str,
    data: dict,
    request: Request,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    """Set the display order for the whole menu in one call.

    Body: {"item_ids": ["menu_products", "menu_new_arrivals", ...]} — the
    list position becomes each item's sort_order. Items not included keep
    their current order (they sort after the listed ones).
    """
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")

    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    item_ids = data.get("item_ids")
    if not isinstance(item_ids, list) or not item_ids:
        raise HTTPException(status_code=400, detail="item_ids (non-empty list) is required")

    applied = 0
    for idx, iid in enumerate(item_ids):
        if upsert_menu_item(menu_key, str(iid).strip(), sort_order=idx):
            applied += 1
    _record_audit(action="menu_reordered", actor=current_admin, resource_type="menu", resource_id=menu_key, details={"menu_key": menu_key, "item_count": applied, "item_ids": [str(i)[:80] for i in item_ids[:100]]})
    invalidate_menu_cache()
    return {"ok": True, "menu_key": menu_key, "reordered": applied}


@router.post("/menus/{menu_key}/{item_id}/delete")
def delete_menu_item_api(
    menu_key: str,
    item_id: str,
    request: Request,
    current_admin: dict = Depends(require_permission("edit_delete_products")),
):
    """Remove an item from the menu.

    - Admin-created items: the DB row is deleted entirely.
    - Code-default items: cannot be removed (they live in code), so they are
      hidden with an inactive override row — they come back on Reset.
    """
    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")

    effective = get_effective_item(menu_key, item_id)
    if not effective:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    if effective["is_default"]:
        upsert_menu_item(menu_key, item_id, is_active=False)
        _record_audit(action="menu_item_deleted", actor=current_admin, resource_type="menu_item", resource_id=f"{menu_key}/{item_id}", details={"menu_key": menu_key, "item_id": item_id, "title": str(effective.get("title", ""))[:120], "hidden": True})
        invalidate_menu_cache()
        return {"ok": True, "menu_key": menu_key, "item_id": item_id, "hidden": True}

    try:
        from database import delete_menu_item
    except Exception:
        def delete_menu_item(mkey, iid):
            with get_db_context() as conn:
                cur = conn.execute(
                    "DELETE FROM menus WHERE menu_key=? AND item_id=?", (mkey, iid)
                )
            return cur.rowcount > 0

    deleted = delete_menu_item(menu_key, item_id)
    invalidate_menu_cache()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    _record_audit(action="menu_item_deleted", actor=current_admin, resource_type="menu_item", resource_id=f"{menu_key}/{item_id}", details={"menu_key": menu_key, "item_id": item_id, "title": str(effective.get("title", ""))[:120], "hidden": False})
    return {"ok": True, "menu_key": menu_key, "item_id": item_id, "hidden": False}


@router.post("/menus/{menu_key}/reset")
def reset_menu_api(menu_key: str, request: Request, current_admin: dict = Depends(require_permission("edit_delete_products"))):
    """Delete DB overrides (items + settings) for one menu; code defaults take effect again."""
    try:
        from backend.services.audit_context import set_audit_actor
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")
    removed = reset_menu(menu_key)
    _record_audit(action="menu_reset", actor=current_admin, resource_type="menu", resource_id=menu_key, details={"menu_key": menu_key, "removed_count": removed})
    invalidate_menu_cache()
    return {"ok": True, "menu_key": menu_key, "removed": removed}


@router.post("/menus/{menu_key}")
def get_menu_api(menu_key: str, current_admin: dict = Depends(get_current_admin)):
    if menu_key not in KNOWN_MENU_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown menu_key: {menu_key}")

    # BUG FIX: this used to return ONLY the raw DB rows once a single edit
    # existed, which made every other menu item vanish from the editor after
    # the first save/toggle. get_menu_editor_items() always merges the code
    # defaults with the DB overrides so the editor sees the complete menu.
    return {
        "menu_key": menu_key,
        "items": get_menu_editor_items(menu_key),
        "settings": get_menu_settings(menu_key),
    }


# ============================================================================
# BROCHURE MANAGEMENT ENDPOINTS
# ============================================================================

class BrochureInfo(BaseModel):
    name: str
    module: str
    description: str = ""
    category: str = ""
    tags: List[str] = []


@router.get("/brochures", dependencies=[Depends(get_current_admin)])
async def list_brochures(tenant_id: str = Query(None)):
    """List all brochures for a tenant or globally."""
    from backend.services.brochure_service import BrochureService
    
    service = BrochureService()
    brochures = service.get_all_brochures(tenant_id)
    
    result = []
    for brochure in brochures:
        result.append({
            "id": brochure.file_id,
            "tenant_id": brochure.tenant_id,
            "module": brochure.module,
            "name": brochure.name,
            "filename": brochure.filename,
            "url": brochure.url,
            "size": brochure.size,
            "keywords": brochure.keywords,
            "metadata": brochure.metadata,
            "created_at": brochure.created_at,
        })
    
    return {"ok": True, "brochures": result, "count": len(result)}


@router.get("/brochures/{brochure_id}", dependencies=[Depends(get_current_admin)])
async def get_brochure(brochure_id: int):
    """Get information about a specific brochure."""
    from backend.services.brochure_service import BrochureService
    
    service = BrochureService()
    
    try:
        row = get_admin_file_row(brochure_id)
        if row:
                brochure = service.Brochure(
                    file_id=row["id"],
                    tenant_id=row["tenant_id"] or "",
                    module=row["module"] or "general",
                    name=row["name"] or "",
                    filename=row["name"] or row.get("filename", ""),
                    url=row["url"] or "",
                    file_path=row["file_path"] or "",
                    ext=row["ext"] or "",
                    size=row["size"] or 0,
                    doc_id=row["doc_id"] or None,
                    created_at=row["created_at"] or "",
                )
                return {
                    "ok": True,
                    "brochure": {
                        "id": brochure.file_id,
                        "tenant_id": brochure.tenant_id,
                        "module": brochure.module,
                        "name": brochure.name,
                        "filename": brochure.filename,
                        "url": brochure.url,
                        "size": brochure.size,
                        "keywords": brochure.keywords,
                        "metadata": brochure.metadata,
                        "created_at": brochure.created_at,
                    }
                }
    except Exception as e:
        logger.error(f"Failed to get brochure {brochure_id}: {e}")
    
    return {"ok": False, "error": f"Brochure {brochure_id} not found"}


@router.delete("/brochures/{brochure_id}", dependencies=[Depends(get_current_admin)])
async def delete_brochure(brochure_id: int, current_admin: dict = Depends(get_current_admin)):
    """Delete a specific brochure."""
    try:
        row = get_admin_file_row(brochure_id)
        if not row:
            return {"ok": False, "error": f"Brochure {brochure_id} not found"}
        if not delete_admin_file_row(brochure_id):
            return {"ok": False, "error": f"Brochure {brochure_id} not found"}
        audit = dict(
            action="brochure_delete",
            actor=current_admin,
            resource_type="brochure",
            resource_id=brochure_id,
            details={"filename": row.get("name", "Unknown"), "module": row.get("module", "unknown")},
        )
        if use_mongodb():
            record_admin_audit_event(None, **audit)
        else:
            with get_db_context() as conn:
                record_admin_audit_event(conn, **audit)
        
        return {"ok": True, "deleted": brochure_id}
        
    except Exception as e:
        logger.error(f"Failed to delete brochure {brochure_id}: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/brochures/upload", dependencies=[Depends(get_current_admin)])
async def upload_brochure(
    file: UploadFile = File(...),
    module: str = Form("catalogue"),
    name: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    tenant_id: str = Form(None),
    current_admin: dict = Depends(get_current_admin)
):
    """Upload a new brochure file."""
    from backend.services.brochure_service import extract_file_metadata
    from backend.services.audit_context import set_audit_actor
    
    # Ensure we have admin permissions
    if not has_permission(current_admin, "upload_files"):
        raise HTTPException(status_code=403, detail="You do not have permission to upload brochures")
    
    if module not in ["catalogue", "new_arrival", "product_brochure", "service_brochure", 
                     "company_profile", "technical_brochure", "pricing", "customer_case_study",
                     "industry_brochure", "general"]:
        return {"ok": False, "error": f"Invalid module. Must be one of: {BROCHURE_MODULES}"}
    
    try:
        set_audit_actor(current_admin)
    except Exception:
        # deliberate: audit attribution is best-effort — the request
        # itself must not fail because the actor could not be stamped.
        logger.debug("AUDIT_ACTOR_SET_SKIPPED | route continues without actor", exc_info=True)
    
    # Read file content
    content = await file.read()
    filename = file.filename or "brochure"
    ext = os.path.splitext(filename)[1].lower()
    
    # Validate file type
    if ext not in SUPPORTED:
        return {"ok": False, "error": f"Unsupported file type: {ext}. Supported: {SUPPORTED}"}
    
    # Save the file
    try:
        # Create upload directory if it doesn't exist
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # Generate unique filename
        import hashlib
        import time
        timestamp = int(time.time())
        file_hash = hashlib.md5(content[:1024]).hexdigest()[:8]
        unique_filename = f"{timestamp}_{file_hash}_{filename}"
        filepath = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        # Extract metadata
        if not name:
            name = filename
        metadata = extract_file_metadata(filename)
        if description:
            metadata['description'] = description
        if category:
            metadata['category'] = category
        if tags:
            metadata['tags'] = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Save to database
        save_admin_file(
            name=name,
            ext=ext.lstrip("."),
            module=module,
            size=len(content),
            file_path=filepath,
            url=None,  # No direct URL, will use file path
            tenant_id=tenant_id,
            actor=current_admin
        )
        
        # Record audit event
        _record_audit(
            action="brochure_upload",
            actor=current_admin,
            resource_type="brochure",
            resource_id=filename,
            details={
                "filename": filename,
                "module": module,
                "size": len(content),
                "metadata": metadata,
            },
        )
        
        return {
            "ok": True,
            "message": "Brochure uploaded successfully",
            "filename": filename,
            "module": module,
            "path": filepath,
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Failed to upload brochure: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/brochures/extract-metadata", dependencies=[Depends(get_current_admin)])
async def extract_brochure_metadata(
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    """Extract metadata from a brochure file for preview."""
    from backend.services.brochure_service import extract_file_metadata
    
    if not has_permission(current_admin, "upload_files"):
        raise HTTPException(status_code=403, detail="You do not have permission to extract metadata")
    
    try:
        # For now, we only extract from filename
        # Could be extended to parse PDF/DOCX content
        filename = file.filename or "brochure"
        metadata = extract_file_metadata(filename)
        
        return {
            "ok": True,
            "filename": filename,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Failed to extract metadata: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/brochures/relevant", dependencies=[Depends(get_current_admin)])
async def find_relevant_brochures(
    query: str = Query(""),
    tenant_id: str = Query(None),
    module: str = Query(None)
):
    """Find brochures relevant to a specific query."""
    from backend.services.brochure_service import BrochureService, categorize_query
    
    service = BrochureService()
    
    if module:
        # Get by specific module
        brochure = service.get_brochure_by_module(module, tenant_id)
        relevant_brochures = [brochure] if brochure else []
    elif query:
        # Categorize query and get relevant brochures
        category = categorize_query(query)
        relevant_brochures = service.get_brochures_by_category(category, tenant_id)
        if not relevant_brochures:
            # Fallback to general search
            relevant_brochures = service.get_all_brochures(tenant_id)
    else:
        # Return all brochures
        relevant_brochures = service.get_all_brochures(tenant_id)
    
    result = []
    for brochure in relevant_brochures:
        result.append({
            "id": brochure.file_id,
            "tenant_id": brochure.tenant_id,
            "module": brochure.module,
            "name": brochure.name,
            "filename": brochure.filename,
            "url": brochure.url,
            "keywords": brochure.keywords,
            "metadata": brochure.metadata,
        })
    
    return {
        "ok": True, 
        "query": query,
        "category": module or (categorize_query(query) if query else "unknown"),
        "brochures": result,
        "count": len(result)
    }


# Available brochure modules for the frontend
BROCHURE_MODULES = [
    "catalogue", "new_arrival", "product_brochure", "service_brochure",
    "company_profile", "technical_brochure", "pricing", "customer_case_study",
    "industry_brochure", "general"
]
