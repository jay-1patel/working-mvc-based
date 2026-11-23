"""Back up and remove uploaded/generated content for one tenant.

This intentionally preserves the tenant registry, admin login, profile/config,
operational history, and audit/error history.  Run without ``--apply`` first.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
ENV_FILE = PROJECT_ROOT / "routing" / ".env"
DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "exports" / "tenant-content-resets"

CONTENT_COLLECTIONS = (
    "admin_files",
    "faq_dataset",
    "knowledge_base",
    "products",
    "tenant_crawl_runs",
    "tenant_crawl_pages",
    "tenant_crawl_images",
    "tenant_crawl_staged",
    "tenant_crawl_schedules",
    "unanswered_queries",
)

PRESERVED_COLLECTIONS = (
    "admins",
    "tenant_profile_versions",
    "tenant_record_columns",
    "customers",
    "chat_history",
    "orders",
    "complaints",
    "leads",
    "campaigns",
    "callbacks",
    "user_states",
    "user_sessions",
    "admin_audit_events",
    "api_error_logs",
    "webhook_logs",
    "whatsapp_send_log",
)

PROFILE_COLLECTIONS = ("draft_config", "published_config", "publish_history")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--apply", action="store_true", help="Perform the reset")
    parser.add_argument(
        "--confirm",
        default="",
        help="Must exactly equal --tenant-id when --apply is used",
    )
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument(
        "--finalize-archive",
        type=Path,
        help="Write a verification manifest into an existing recovery archive",
    )
    return parser.parse_args()


def _database():
    load_dotenv(ENV_FILE, override=True)
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError(f"MONGODB_URI is missing from {ENV_FILE}")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    configured = os.environ.get("MONGODB_DATABASE", "").strip()
    database_name = configured or client.get_default_database().name
    return client, client[database_name]


def _count_map(db, collections: tuple[str, ...], tenant_id: str) -> dict[str, int]:
    existing = set(db.list_collection_names())
    return {
        name: db[name].count_documents({"tenant_id": tenant_id}) if name in existing else 0
        for name in collections
    }


def _profile_count_map(db, tenant_id: str) -> dict[str, int]:
    existing = set(db.list_collection_names())
    scope = f"tenant_profile:{tenant_id}"
    return {
        name: db[name].count_documents({"scope": scope}) if name in existing else 0
        for name in PROFILE_COLLECTIONS
    }


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _source_files(db, tenant_id: str) -> list[Path]:
    upload_root = (BACKEND_DIR / "uploaded_files").resolve()
    result: list[Path] = []
    seen: set[str] = set()
    for row in db.admin_files.find({"tenant_id": tenant_id}, {"file_path": 1}):
        raw = str(row.get("file_path") or "").strip()
        if not raw:
            continue
        path = Path(raw).resolve()
        key = os.path.normcase(str(path))
        if key in seen or not path.is_file() or not _inside(path, upload_root):
            continue
        other_refs = db.admin_files.count_documents(
            {"file_path": raw, "tenant_id": {"$ne": tenant_id}}
        )
        if other_refs:
            continue
        seen.add(key)
        result.append(path)
    return sorted(result, key=lambda item: str(item).lower())


def _file_inventory(db, tenant_id: str) -> dict[str, Any]:
    roots = {
        "knowledge": PROJECT_ROOT / "data" / "tenants" / tenant_id / "knowledge",
        "crawl_images": BACKEND_DIR / "uploaded_files" / "crawl_images" / tenant_id,
    }
    result: dict[str, Any] = {"directories": {}, "source_files": []}
    for label, root in roots.items():
        files = [path for path in root.rglob("*") if path.is_file()] if root.is_dir() else []
        result["directories"][label] = {
            "path": str(root),
            "files": len(files),
            "bytes": sum(path.stat().st_size for path in files),
        }
    for path in _source_files(db, tenant_id):
        result["source_files"].append({"path": str(path), "bytes": path.stat().st_size})
    return result


def _write_json(path: Path, value: Any, *, bson: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if bson:
        path.write_text(json_util.dumps(value, indent=2), encoding="utf-8")
    else:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )


def _copy_recovery_files(db, tenant_id: str, archive: Path) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    directories = (
        (PROJECT_ROOT / "data" / "tenants" / tenant_id / "knowledge", "knowledge"),
        (BACKEND_DIR / "uploaded_files" / "crawl_images" / tenant_id, "crawl_images"),
    )
    for source, label in directories:
        if not source.is_dir():
            continue
        destination = archive / "files" / label
        shutil.copytree(source, destination)
        copied.append({"source": str(source), "archive": str(destination), "kind": "directory"})

    upload_root = (BACKEND_DIR / "uploaded_files").resolve()
    for source in _source_files(db, tenant_id):
        relative = source.resolve().relative_to(upload_root)
        destination = archive / "files" / "uploaded_sources" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append({"source": str(source), "archive": str(destination), "kind": "file"})
    return copied


def _backup_documents(db, tenant_id: str, archive: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    existing = set(db.list_collection_names())
    for name in CONTENT_COLLECTIONS:
        rows = list(db[name].find({"tenant_id": tenant_id})) if name in existing else []
        _write_json(archive / "mongo" / f"{name}.json", rows, bson=True)
        counts[name] = len(rows)
    return counts


def main() -> int:
    args = _args()
    tenant_id = str(args.tenant_id or "").strip()
    if not tenant_id or tenant_id in {".", ".."} or any(ch in tenant_id for ch in "/\\"):
        raise SystemExit("Unsafe tenant id")
    if args.apply and args.confirm != tenant_id:
        raise SystemExit("--confirm must exactly match --tenant-id when using --apply")
    if args.apply and args.finalize_archive:
        raise SystemExit("Use either --apply or --finalize-archive, not both")

    client, db = _database()
    try:
        tenant = db.tenants.find_one({"id": tenant_id}, {"_id": 0})
        if not tenant:
            raise SystemExit(f"Tenant {tenant_id!r} does not exist in {db.name}.tenants")

        before_content = _count_map(db, CONTENT_COLLECTIONS, tenant_id)
        before_preserved = _count_map(db, PRESERVED_COLLECTIONS, tenant_id)
        before_profiles = _profile_count_map(db, tenant_id)
        files = _file_inventory(db, tenant_id)
        report = {
            "mode": "apply" if args.apply else "dry-run",
            "database": db.name,
            "tenant_id": tenant_id,
            "tenant": tenant,
            "content_counts": before_content,
            "preserved_counts": before_preserved,
            "profile_counts": before_profiles,
            "files": files,
        }
        print(json.dumps(report, indent=2, default=str))
        if args.finalize_archive:
            archive_root = args.archive_root.resolve()
            archive = args.finalize_archive.resolve()
            if not _inside(archive, archive_root) or not archive.is_dir():
                raise RuntimeError(f"Invalid recovery archive: {archive}")
            if not archive.name.startswith(f"tenant-{tenant_id}-"):
                raise RuntimeError(f"Archive does not belong to tenant {tenant_id}: {archive}")
            if not (archive / "mongo").is_dir() or not (archive / "files").is_dir():
                raise RuntimeError(f"Incomplete recovery archive: {archive}")
            if any(before_content.values()):
                raise RuntimeError("Content is not empty; refusing to finalize reset archive")
            recovered_files = [path for path in archive.rglob("*") if path.is_file()]
            manifest = {
                **report,
                "status": "reset_complete",
                "archive": str(archive),
                "recovered_after_manifest_write_error": True,
                "archive_file_count": len(recovered_files),
                "archive_bytes": sum(path.stat().st_size for path in recovered_files),
                "verification": {
                    "tenant_rows": db.tenants.count_documents({"id": tenant_id}),
                    "content_counts": before_content,
                    "preserved_counts": before_preserved,
                    "profile_counts": before_profiles,
                },
            }
            _write_json(archive / "manifest.json", manifest)
            print(json.dumps({"status": "archive_finalized", "archive": str(archive)}, indent=2))
            return 0
        if not args.apply:
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archive_root = args.archive_root.resolve()
        archive = archive_root / f"tenant-{tenant_id}-{stamp}"
        if archive.exists() or archive_root in {PROJECT_ROOT.resolve(), Path(archive_root.anchor)}:
            raise RuntimeError(f"Unsafe archive location: {archive}")
        archive.mkdir(parents=True)

        copied = _copy_recovery_files(db, tenant_id, archive)
        backup_counts = _backup_documents(db, tenant_id, archive)
        if backup_counts != before_content:
            raise RuntimeError("Database changed during backup; reset aborted before deletion")

        deletion_counts: dict[str, int] = {}
        for name in CONTENT_COLLECTIONS:
            deletion_counts[name] = db[name].delete_many({"tenant_id": tenant_id}).deleted_count

        # Resolve source paths from the archived manifest after metadata deletion.
        removed_files: list[str] = []
        knowledge = (PROJECT_ROOT / "data" / "tenants" / tenant_id / "knowledge").resolve()
        crawl_images = (BACKEND_DIR / "uploaded_files" / "crawl_images" / tenant_id).resolve()
        for path, expected_parent, recreate in (
            (knowledge, (PROJECT_ROOT / "data" / "tenants" / tenant_id).resolve(), True),
            (crawl_images, (BACKEND_DIR / "uploaded_files" / "crawl_images").resolve(), False),
        ):
            if path.parent != expected_parent:
                raise RuntimeError(f"Refusing unsafe directory removal: {path}")
            if path.is_dir():
                shutil.rmtree(path)
                removed_files.append(str(path))
            if recreate:
                path.mkdir(parents=True, exist_ok=True)
        for item in copied:
            if item["kind"] != "file":
                continue
            source = Path(item["source"]).resolve()
            upload_root = (BACKEND_DIR / "uploaded_files").resolve()
            if source.is_file() and _inside(source, upload_root):
                source.unlink()
                removed_files.append(str(source))

        after_content = _count_map(db, CONTENT_COLLECTIONS, tenant_id)
        after_preserved = _count_map(db, PRESERVED_COLLECTIONS, tenant_id)
        after_profiles = _profile_count_map(db, tenant_id)
        tenant_after = db.tenants.count_documents({"id": tenant_id})
        if any(after_content.values()):
            raise RuntimeError(f"Content verification failed: {after_content}")
        if after_preserved != before_preserved or after_profiles != before_profiles:
            raise RuntimeError("A preserved collection changed unexpectedly")
        if tenant_after != 1 or after_preserved.get("admins", 0) < 1:
            raise RuntimeError("Tenant or admin preservation check failed")

        manifest = {
            **report,
            "archive": str(archive),
            "copied_files": copied,
            "backup_counts": backup_counts,
            "deletion_counts": deletion_counts,
            "removed_files": removed_files,
            "verification": {
                "tenant_rows": tenant_after,
                "content_counts": after_content,
                "preserved_counts": after_preserved,
                "profile_counts": after_profiles,
            },
        }
        _write_json(archive / "manifest.json", manifest)
        print(json.dumps({"status": "reset_complete", "archive": str(archive)}, indent=2))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
