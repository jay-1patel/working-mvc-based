#!/usr/bin/env python3
"""Phase 2 — import file-only tenant data into the database.

- Config values that exist ONLY in clients/<id>/config.json go into the
  tenant's published database config. DATABASE ALWAYS WINS: never overwrite
  a DB value with a file value; report conflicts instead.
- Knowledge .md files that exist only on disk (clients/ or data/tenants/)
  become knowledge_base documents in the same chunk format as
  kb.services.rag.add_document_to_kb, WITH embeddings generated and verified.

Idempotent (dedupe by tenant + content hash / source filename).
Defaults to DRY-RUN; writes only with --apply.

Usage:
  python scripts/migrate_file_stores_to_db.py
  python scripts/migrate_file_stores_to_db.py --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

load_dotenv(REPO_ROOT / "routing" / ".env")

from shared.tenancy.paths import BACKEND_CLIENTS_DIR, CLIENTS_DIR  # noqa: E402


def _mongo():
    from pymongo import MongoClient

    uri = os.environ["MONGODB_URI"]
    dbn = os.environ.get("MONGODB_DATABASE", "tmpdbtest")
    return MongoClient(uri, serverSelectionTimeoutMS=8000)[dbn]


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _normalize_ws(text: str) -> str:
    return "\n".join(
        line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")
    ).strip()


def _flatten_keys(obj: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(_flatten_keys(v, key))
            elif isinstance(v, list):
                out[key] = v
            else:
                out[key] = v
    else:
        out[prefix or "value"] = obj
    return out


def _unflatten(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild nested dict from dotted keys (only for missing-key inserts)."""
    root: Dict[str, Any] = {}
    for dotted, value in flat.items():
        parts = dotted.split(".")
        cur = root
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
            if not isinstance(cur, dict):
                break
        else:
            if isinstance(cur, dict):
                cur[parts[-1]] = value
    return root


def _list_tenant_folders() -> List[str]:
    names: Set[str] = set()
    for root in (CLIENTS_DIR, BACKEND_CLIENTS_DIR):
        if root.is_dir():
            for p in root.iterdir():
                if p.is_dir() and not p.name.startswith("."):
                    names.add(p.name)
    return sorted(names)


def _resolve_tenant_id(folder: str) -> str:
    from shared.tenancy import store

    for t in store.list_tenants():
        tid = str(t.get("id") or "")
        slug = str(t.get("slug") or "")
        if folder in {tid, slug}:
            return tid
    return folder


def _ensure_tenant_registered(tenant_id: str, folder: str, apply: bool) -> bool:
    """Return True if tenant exists (or was created). File-only orphan folders
    need a registry row before publish_version will accept them."""
    from shared.tenancy import store

    if store.get_tenant(tenant_id):
        return True
    if not apply:
        print(f"  [dry-run] would ensure_tenant id={tenant_id} (from folder {folder})")
        return True
    try:
        store.ensure_tenant(
            tenant_id,
            slug=folder,
            display_name=folder,
            vertical="generic",
            status="active",
        )
        print(f"  registered tenant id={tenant_id}")
        return True
    except Exception as exc:
        print(f"  FAILED ensure_tenant {tenant_id}: {exc}")
        return False


def _db_content_hashes(db, tenant_id: str) -> Set[str]:
    hashes: Set[str] = set()
    for row in db.knowledge_base.find({"tenant_id": tenant_id}):
        content = row.get("content") or ""
        chunks = row.get("chunks_json")
        if isinstance(chunks, str):
            try:
                chunks = json.loads(chunks)
            except Exception:
                chunks = None
        joined = "\n\n".join(chunks) if isinstance(chunks, list) and chunks else content
        for blob in {content, joined}:
            norm = _normalize_ws(blob)
            if norm:
                hashes.add(_sha256_text(norm))
    return hashes


def _db_sources(db, tenant_id: str) -> Set[str]:
    sources: Set[str] = set()
    for row in db.knowledge_base.find({"tenant_id": tenant_id}, {"source": 1, "title": 1}):
        for key in ("source", "title"):
            val = row.get(key)
            if val:
                sources.add(str(val).strip().lower())
                sources.add(Path(str(val)).name.lower())
                sources.add(Path(str(val)).stem.lower())
    return sources


def _iter_knowledge_files(tenant_folder: str) -> List[Tuple[str, Path]]:
    files: List[Tuple[str, Path]] = []
    seen: Set[str] = set()
    for origin, root in (
        ("clients", CLIENTS_DIR / tenant_folder / "knowledge"),
        ("data/tenants", BACKEND_CLIENTS_DIR / tenant_folder / "knowledge"),
    ):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            key = path.name.lower()
            # Prefer data/tenants if same filename exists in both
            if key in seen and origin == "clients":
                continue
            seen.add(key)
            files.append((origin, path))
    return files


def _import_knowledge_file(
    db,
    tenant_id: str,
    path: Path,
    *,
    apply: bool,
    content_hashes: Set[str],
    sources: Set[str],
) -> str:
    """Return status: imported | already-present | failed."""
    text = path.read_text(encoding="utf-8")
    norm = _normalize_ws(text)
    if not norm:
        return "failed"
    sha = _sha256_text(norm)
    source_name = path.name
    if sha in content_hashes or source_name.lower() in sources or path.stem.lower() in sources:
        return "already-present"

    if not apply:
        return "imported"  # would import

    from kb.services.rag import add_document_to_kb

    result = add_document_to_kb(
        filename=source_name,
        text=norm,
        category="migrated_from_file",
        tenant_id=tenant_id,
    )
    if not result.get("success"):
        print(f"    FAIL add_document_to_kb {source_name}: {result.get('error')}")
        return "failed"

    doc_id = result.get("doc_id")
    # Verify embeddings exist
    row = db.knowledge_base.find_one({"id": doc_id})
    if not row or not row.get("embedding_blob"):
        # Known trap: empty chunks_json skips embedding generation.
        # add_document_to_kb should have written embeddings; if missing, fail.
        print(f"    FAIL no embedding_blob after import doc_id={doc_id} file={source_name}")
        return "failed"

    chunks = row.get("chunks_json")
    if isinstance(chunks, str):
        try:
            chunks = json.loads(chunks)
        except Exception:
            chunks = []
    if not chunks:
        print(f"    FAIL empty chunks_json doc_id={doc_id} file={source_name}")
        return "failed"

    content_hashes.add(sha)
    sources.add(source_name.lower())
    sources.add(path.stem.lower())
    return "imported"


def _merge_missing_config(
    tenant_id: str,
    file_config: Dict[str, Any],
    *,
    apply: bool,
) -> Tuple[int, int, int]:
    """Import file-only config keys into published DB. Returns
    (imported, already-present, conflicts)."""
    from shared.tenancy import store, loader

    published = store.get_current_payload(tenant_id) or {}
    if isinstance(published.get("tenant_profile"), dict):
        published = published["tenant_profile"]
    if not isinstance(published, dict):
        published = {}

    # Strip wrapper from file
    file_layer = file_config
    if isinstance(file_layer.get("tenant_profile"), dict):
        file_layer = file_layer["tenant_profile"]

    pub_flat = _flatten_keys(published)
    file_flat = _flatten_keys(file_layer)

    imported = 0
    already = 0
    conflicts = 0
    additions: Dict[str, Any] = {}

    for key, fval in file_flat.items():
        if key.startswith("_"):
            continue
        if key not in pub_flat:
            additions[key] = fval
            imported += 1
        else:
            dbval = pub_flat[key]
            if json.dumps(fval, sort_keys=True, default=str) != json.dumps(
                dbval, sort_keys=True, default=str
            ):
                conflicts += 1
                print(f"    CONFLICT config.{key}: keeping DB value")
            else:
                already += 1

    if not additions:
        return imported, already, conflicts

    if not apply:
        print(f"    [dry-run] would add {len(additions)} config keys: {list(additions.keys())[:12]}")
        return imported, already, conflicts

    # Deep-merge only the missing keys into a new published payload
    addition_tree = _unflatten(additions)
    from shared.tenancy.merge import merge_layers

    # DB wins: merge file additions UNDER published so published overrides
    # any accidental overlap (we already filtered to missing keys only).
    merged = merge_layers(addition_tree, published)
    merged["tenant_id"] = tenant_id
    store.publish_version(tenant_id, merged, published_by="migrate_file_stores_to_db")
    try:
        loader.reload_profile(tenant_id)
    except Exception:
        pass
    print(f"    published config with {len(additions)} new keys")
    return imported, already, conflicts


def migrate_tenant(folder: str, db, *, apply: bool) -> Dict[str, Any]:
    tenant_id = _resolve_tenant_id(folder)
    print(f"\n=== {folder} (db tenant_id={tenant_id}) apply={apply} ===")

    counts = {
        "tenant_id": tenant_id,
        "folder": folder,
        "config_imported": 0,
        "config_already_present": 0,
        "config_conflicts": 0,
        "knowledge_imported": 0,
        "knowledge_already_present": 0,
        "knowledge_failed": 0,
        "imported": 0,
        "already_present": 0,
        "conflicts": 0,
    }

    if not _ensure_tenant_registered(tenant_id, folder, apply):
        counts["knowledge_failed"] = -1
        return counts

    # Config
    config_path = CLIENTS_DIR / folder / "config.json"
    if config_path.is_file():
        try:
            file_config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  skip config: {exc}")
            file_config = None
        if isinstance(file_config, dict):
            ci, ca, cc = _merge_missing_config(tenant_id, file_config, apply=apply)
            counts["config_imported"] = ci
            counts["config_already_present"] = ca
            counts["config_conflicts"] = cc
    else:
        print("  no clients/.../config.json")

    # Knowledge
    content_hashes = _db_content_hashes(db, tenant_id)
    sources = _db_sources(db, tenant_id)
    files = _iter_knowledge_files(folder)
    print(f"  knowledge files on disk: {len(files)}")

    for origin, path in files:
        status = _import_knowledge_file(
            db,
            tenant_id,
            path,
            apply=apply,
            content_hashes=content_hashes,
            sources=sources,
        )
        if status == "imported":
            counts["knowledge_imported"] += 1
            print(f"    {status}: [{origin}] {path.name}")
        elif status == "already-present":
            counts["knowledge_already_present"] += 1
        else:
            counts["knowledge_failed"] += 1
            print(f"    {status}: [{origin}] {path.name}")

    if apply and counts["knowledge_imported"]:
        try:
            from kb.services.rag import rebuild_faiss_index

            rebuild_faiss_index()
            print("  rebuilt FAISS index")
        except Exception as exc:
            print(f"  WARN rebuild_faiss_index: {exc}")

    counts["imported"] = counts["config_imported"] + counts["knowledge_imported"]
    counts["already_present"] = (
        counts["config_already_present"] + counts["knowledge_already_present"]
    )
    counts["conflicts"] = counts["config_conflicts"]
    print(
        f"  TOTALS imported={counts['imported']} already-present={counts['already_present']} "
        f"conflicts={counts['conflicts']} kb_failed={counts['knowledge_failed']}"
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to the database (default is dry-run)",
    )
    parser.add_argument("--tenants", nargs="*", default=None)
    parser.add_argument(
        "--json",
        default=str(REPO_ROOT / "reports" / "file_store_migration.json"),
    )
    args = parser.parse_args()

    db = _mongo()
    folders = args.tenants or _list_tenant_folders()
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Folders: {folders}")

    results = []
    for folder in folders:
        results.append(migrate_tenant(folder, db, apply=args.apply))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "apply": bool(args.apply),
        "tenants": results,
        "totals": {
            "imported": sum(r["imported"] for r in results),
            "already_present": sum(r["already_present"] for r in results),
            "conflicts": sum(r["conflicts"] for r in results),
            "knowledge_failed": sum(r["knowledge_failed"] for r in results),
        },
    }
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\nWrote {out}")
    print("TOTALS", report["totals"])
    return 0 if report["totals"]["knowledge_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
