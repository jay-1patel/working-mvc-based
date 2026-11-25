"""Event facility pins (medical, police, ambulance, etc.) — Mongo-backed."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .core import use_mongodb

logger = logging.getLogger("db.event_facilities")


def _repo():
    from .mongo import Repository
    return Repository("event_facilities")


def list_event_facilities(
    tenant_id: str,
    *,
    event: str | None = None,
    facility_type: str | None = None,
    active_only: bool = True,
) -> list[dict]:
    tid = str(tenant_id or "").strip()
    if not tid:
        return []
    if not use_mongodb():
        logger.warning("event_facilities requires MongoDB")
        return []
    filt: dict[str, Any] = {"tenant_id": tid}
    if event:
        filt["event"] = str(event).strip()
    if facility_type:
        filt["type"] = str(facility_type).strip()
    if active_only:
        filt["is_active"] = 1
    rows = _repo().find_all(filt, sort=[("sort_order", 1), ("id", 1)])
    return [dict(r) for r in (rows or [])]


def get_event_facility(facility_id: int | str, *, tenant_id: str | None = None) -> Optional[dict]:
    if not use_mongodb():
        return None
    try:
        fid = int(facility_id)
    except (TypeError, ValueError):
        return None
    filt: dict[str, Any] = {"id": fid}
    if tenant_id:
        filt["tenant_id"] = str(tenant_id).strip()
    row = _repo().find_one(filt)
    return dict(row) if row else None


def create_event_facility(payload: dict) -> dict:
    if not use_mongodb():
        raise RuntimeError("event_facilities requires MongoDB")
    now = datetime.now(timezone.utc)
    doc = {
        "tenant_id": str(payload.get("tenant_id") or "").strip(),
        "event": str(payload.get("event") or "").strip(),
        "type": str(payload.get("type") or "").strip(),
        "name": str(payload.get("name") or "").strip(),
        "address": str(payload.get("address") or "").strip(),
        "latitude": float(payload["latitude"]),
        "longitude": float(payload["longitude"]),
        "message": str(payload.get("message") or "").strip(),
        "is_active": 1 if payload.get("is_active", 1) else 0,
        "sort_order": int(payload.get("sort_order") or 0),
        "created_at": now,
        "updated_at": now,
    }
    if not doc["tenant_id"] or not doc["event"] or not doc["type"] or not doc["name"]:
        raise ValueError("tenant_id, event, type and name are required")
    row = _repo().insert(doc)
    return dict(row)


def update_event_facility(
    facility_id: int | str,
    changes: dict,
    *,
    tenant_id: str | None = None,
) -> Optional[dict]:
    if not use_mongodb():
        raise RuntimeError("event_facilities requires MongoDB")
    existing = get_event_facility(facility_id, tenant_id=tenant_id)
    if not existing:
        return None
    allowed = {
        "event", "type", "name", "address", "latitude", "longitude",
        "message", "is_active", "sort_order",
    }
    patch: dict[str, Any] = {}
    for key in allowed:
        if key not in changes:
            continue
        val = changes[key]
        if key in {"latitude", "longitude"}:
            patch[key] = float(val)
        elif key in {"is_active", "sort_order"}:
            patch[key] = int(val)
        else:
            patch[key] = str(val or "").strip()
    patch["updated_at"] = datetime.now(timezone.utc)
    _repo().update({"id": int(existing["id"])}, patch)
    return get_event_facility(existing["id"], tenant_id=tenant_id)


def delete_event_facility(
    facility_id: int | str,
    *,
    tenant_id: str | None = None,
    hard: bool = False,
) -> bool:
    if not use_mongodb():
        raise RuntimeError("event_facilities requires MongoDB")
    existing = get_event_facility(facility_id, tenant_id=tenant_id)
    if not existing:
        return False
    if hard:
        _repo().delete({"id": int(existing["id"])})
    else:
        _repo().update(
            {"id": int(existing["id"])},
            {"is_active": 0, "updated_at": datetime.now(timezone.utc)},
        )
    return True
