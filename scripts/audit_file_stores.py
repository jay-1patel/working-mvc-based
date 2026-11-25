#!/usr/bin/env python3
"""Phase 1 — read-only audit of file-based tenant stores vs the database.

For every tenant folder under clients/ and data/tenants/, list:
  - config.json keys/values (clients/<id>/config.json)
  - knowledge/*.md under clients/<id>/knowledge/ and data/tenants/<id>/knowledge/
and compare against the tenant's published DB config and knowledge_base docs.

Reports per tenant what exists ONLY in files (the set Phase 2 must import).
Change nothing.

Usage:
  python scripts/audit_file_stores.py
  python scripts/audit_file_stores.py --json reports/file_store_audit.json
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
    return "\n".join(line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")).strip()


def _flatten_keys(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dicts to dotted keys; lists become JSON strings for compare."""
    out: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(_flatten_keys(v, key))
            elif isinstance(v, list):
                out[key] = json.dumps(v, sort_keys=True, default=str)
            else:
                out[key] = v
    else:
        out[prefix or "value"] = obj
    return out


def _list_tenant_dirs(root: Path) -> List[str]:
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def _read_config(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {"_non_object": data}
    except Exception as exc:
        return {"_read_error": str(exc)}


def _knowledge_files(knowledge_dir: Path) -> List[Dict[str, Any]]:
    if not knowledge_dir.is_dir():
        return []
    rows = []
    for path in sorted(knowledge_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            rows.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "error": str(exc),
                    "sha256": None,
                    "chars": 0,
                }
            )
            continue
        norm = _normalize_ws(text)
        rows.append(
            {
                "filename": path.name,
                "path": str(path),
                "sha256": _sha256_text(norm),
                "chars": len(norm),
                "preview": norm[:160].replace("\n", " "),
            }
        )
    return rows


def _db_knowledge_index(db, tenant_id: str) -> Dict[str, Dict[str, Any]]:
    """Map content sha256 -> doc metadata for a tenant."""
    index: Dict[str, Dict[str, Any]] = {}
    for row in db.knowledge_base.find({"tenant_id": tenant_id}):
        content = row.get("content") or ""
        # Also hash joined chunks if present
        chunks = row.get("chunks_json")
        if isinstance(chunks, str):
            try:
                chunks = json.loads(chunks)
            except Exception:
                chunks = None
        joined = "\n\n".join(chunks) if isinstance(chunks, list) and chunks else content
        for blob in {content, joined}:
            norm = _normalize_ws(blob)
            if not norm:
                continue
            index[_sha256_text(norm)] = {
                "id": row.get("id"),
                "source": row.get("source"),
                "title": row.get("title"),
                "has_embedding": row.get("embedding_blob") is not None,
            }
        # Also index by source filename stem for soft matching reports
    return index


def _db_knowledge_sources(db, tenant_id: str) -> Set[str]:
    sources: Set[str] = set()
    for row in db.knowledge_base.find({"tenant_id": tenant_id}, {"source": 1, "title": 1}):
        for key in ("source", "title"):
            val = row.get(key)
            if val:
                sources.add(str(val).strip().lower())
                sources.add(Path(str(val)).stem.lower())
    return sources


def _published_config(db, tenant_id: str) -> Dict[str, Any]:
    from shared.tenancy import store

    payload = store.get_current_payload(tenant_id) or {}
    if isinstance(payload, dict) and isinstance(payload.get("tenant_profile"), dict):
        payload = payload["tenant_profile"]
    return payload if isinstance(payload, dict) else {}


def _resolve_db_tenant_ids(db, folder_name: str) -> List[str]:
    """Map a disk folder name to zero-or-more DB tenant ids (id or slug)."""
    from shared.tenancy import store

    matches = []
    for t in store.list_tenants():
        tid = str(t.get("id") or "")
        slug = str(t.get("slug") or "")
        if folder_name in {tid, slug}:
            matches.append(tid)
    # Also accept folder name as a synthetic id even if not registered
    if not matches:
        # Check knowledge_base / faq for orphan tenant_id matching folder
        if db.knowledge_base.count_documents({"tenant_id": folder_name}) or db.faq_dataset.count_documents(
            {"tenant_id": folder_name}
        ):
            matches.append(folder_name)
    return matches or [folder_name]


def audit_tenant(
    folder_name: str,
    db,
    *,
    clients_root: Path,
    backend_root: Path,
) -> Dict[str, Any]:
    clients_dir = clients_root / folder_name
    backend_dir = backend_root / folder_name
    config_path = clients_dir / "config.json"
    file_config = _read_config(config_path)

    clients_knowledge = _knowledge_files(clients_dir / "knowledge")
    backend_knowledge = _knowledge_files(backend_dir / "knowledge")

    db_tenant_ids = _resolve_db_tenant_ids(db, folder_name)
    primary_tid = db_tenant_ids[0]

    published = _published_config(db, primary_tid)
    pub_flat = _flatten_keys(published)
    file_flat = _flatten_keys(file_config) if isinstance(file_config, dict) and "_read_error" not in file_config else {}

    config_only_in_files: Dict[str, Any] = {}
    config_conflicts: Dict[str, Any] = {}
    config_in_both_same: List[str] = []

    if file_flat:
        for key, fval in file_flat.items():
            if key.startswith("_"):
                continue
            if key not in pub_flat:
                config_only_in_files[key] = fval
            else:
                dbval = pub_flat[key]
                if json.dumps(fval, sort_keys=True, default=str) != json.dumps(
                    dbval, sort_keys=True, default=str
                ):
                    config_conflicts[key] = {"file": fval, "database": dbval}
                else:
                    config_in_both_same.append(key)

    # Knowledge: file-only by content hash and by filename stem
    kb_index: Dict[str, Dict[str, Any]] = {}
    kb_sources: Set[str] = set()
    for tid in db_tenant_ids:
        kb_index.update(_db_knowledge_index(db, tid))
        kb_sources |= _db_knowledge_sources(db, tid)

    def classify_knowledge(files: List[Dict[str, Any]], origin: str) -> Dict[str, Any]:
        only_files = []
        already = []
        for f in files:
            sha = f.get("sha256")
            stem = Path(f["filename"]).stem.lower()
            fname = f["filename"].lower()
            in_db_by_hash = bool(sha and sha in kb_index)
            in_db_by_name = fname in kb_sources or stem in kb_sources
            entry = {**f, "origin": origin, "matched_db": kb_index.get(sha) if sha else None}
            if in_db_by_hash or in_db_by_name:
                already.append(entry)
            else:
                only_files.append(entry)
        return {"only_in_files": only_files, "already_in_db": already}

    clients_kb = classify_knowledge(clients_knowledge, "clients")
    backend_kb = classify_knowledge(backend_knowledge, "data/tenants")

    file_only_count = (
        len(config_only_in_files)
        + len(clients_kb["only_in_files"])
        + len(backend_kb["only_in_files"])
    )

    return {
        "folder": folder_name,
        "db_tenant_ids": db_tenant_ids,
        "paths": {
            "clients_dir": str(clients_dir),
            "clients_exists": clients_dir.is_dir(),
            "config_json": str(config_path),
            "config_exists": config_path.is_file(),
            "backend_dir": str(backend_dir),
            "backend_exists": backend_dir.is_dir(),
        },
        "config": {
            "file_keys": sorted(file_flat.keys()) if file_flat else [],
            "file_values": file_config,
            "published_keys": sorted(pub_flat.keys()),
            "only_in_files": config_only_in_files,
            "conflicts": config_conflicts,
            "same_in_both": config_in_both_same,
        },
        "knowledge": {
            "clients": {
                "count": len(clients_knowledge),
                **clients_kb,
            },
            "data_tenants": {
                "count": len(backend_knowledge),
                **backend_kb,
            },
        },
        "file_only_summary": {
            "config_keys": len(config_only_in_files),
            "config_conflicts": len(config_conflicts),
            "knowledge_clients": len(clients_kb["only_in_files"]),
            "knowledge_data_tenants": len(backend_kb["only_in_files"]),
            "total_file_only_items": file_only_count,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit file tenant stores vs DB (read-only)")
    parser.add_argument(
        "--json",
        default=str(REPO_ROOT / "reports" / "file_store_audit.json"),
        help="Write full JSON report here",
    )
    parser.add_argument("--clients-dir", default=str(CLIENTS_DIR))
    parser.add_argument("--backend-clients-dir", default=str(BACKEND_CLIENTS_DIR))
    args = parser.parse_args()

    clients_root = Path(args.clients_dir)
    backend_root = Path(args.backend_clients_dir)

    db = _mongo()
    from shared.tenancy import store

    disk_folders = sorted(
        set(_list_tenant_dirs(clients_root)) | set(_list_tenant_dirs(backend_root))
    )
    db_tenants = [t["id"] for t in store.list_tenants()]
    # Also audit DB tenants that have no disk folder (report empty file-only)
    all_names = sorted(set(disk_folders) | set(db_tenants))

    print(f"CLIENTS_DIR={clients_root} exists={clients_root.is_dir()}")
    print(f"BACKEND_CLIENTS_DIR={backend_root} exists={backend_root.is_dir()}")
    print(f"Disk folders: {disk_folders}")
    print(f"DB tenants: {db_tenants}")
    print(f"Auditing: {all_names}")

    tenants_report = []
    total_file_only = 0
    for name in all_names:
        row = audit_tenant(name, db, clients_root=clients_root, backend_root=backend_root)
        tenants_report.append(row)
        s = row["file_only_summary"]
        total_file_only += s["total_file_only_items"]
        print(
            f"\n=== {name} === file-only: config_keys={s['config_keys']} "
            f"kb_clients={s['knowledge_clients']} kb_data={s['knowledge_data_tenants']} "
            f"conflicts={s['config_conflicts']}"
        )
        if s["config_keys"]:
            print(f"  config only-in-files keys: {list(row['config']['only_in_files'].keys())[:20]}")
        for origin_key, label in (
            ("clients", "clients/knowledge"),
            ("data_tenants", "data/tenants/knowledge"),
        ):
            only = row["knowledge"][origin_key]["only_in_files"]
            if only:
                print(f"  {label} only-in-files ({len(only)}):")
                for f in only[:15]:
                    print(f"    - {f['filename']} chars={f.get('chars')} sha={str(f.get('sha256'))[:12]}")
                if len(only) > 15:
                    print(f"    ... +{len(only) - 15} more")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clients_dir": str(clients_root),
        "backend_clients_dir": str(backend_root),
        "disk_folders": disk_folders,
        "db_tenants": db_tenants,
        "tenants": tenants_report,
        "totals": {
            "tenants_audited": len(tenants_report),
            "total_file_only_items": total_file_only,
            "tenants_with_file_only": sum(
                1 for t in tenants_report if t["file_only_summary"]["total_file_only_items"] > 0
            ),
        },
    }

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\nTOTAL file-only items: {total_file_only}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
