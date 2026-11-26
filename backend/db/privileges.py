"""Menu privilege catalog + per-user grants (Send2-style tables).

Collections:
  - ``menu_privilege`` — catalog (id, menu_name, permission, flag)
  - ``menu_set_privilege`` — grants (id uuid, user_id, privileges_id,
    privileges_name, flag)

Superadmin (customer_care / id 3042) always has every active menu.
New admins have no ``menu_set_privilege`` rows until a superadmin assigns some.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .core import logger, use_mongodb

# Seeded catalog entries: fixed numeric ids + permission keys.
MENU_PRIVILEGE_SEED = (
    (1, "graphic", "graphic"),
    (2, "chats", "chats"),
    (3, "profile", "profile"),
    (4, "customer", "customer"),
    (5, "website_crawler", "website_crawler"),
    (6, "setup_chatbot", "setup_chatbot"),
    (7, "menu", "menu"),
)

MENU_PRIVILEGE_KEYS = tuple(permission for _, _, permission in MENU_PRIVILEGE_SEED)

MENU_PRIVILEGE_META = {
    "graphic": {
        "label": "Graphic",
        "description": "Access the dashboard overview and analytics graphics.",
    },
    "chats": {
        "label": "Chats",
        "description": "View and manage live WhatsApp chats and inbox.",
    },
    "profile": {
        "label": "Profile",
        "description": "View and edit the company profile and brand details.",
    },
    "customer": {
        "label": "Customer",
        "description": "View and manage customer records.",
    },
    "website_crawler": {
        "label": "Website crawler",
        "description": "Crawl websites and manage crawled knowledge content.",
    },
    "setup_chatbot": {
        "label": "Setup chatbot",
        "description": "Configure and set up the chatbot for the tenant.",
    },
    "menu": {
        "label": "Menu",
        "description": "Manage the WhatsApp menu and catalogue items.",
    },
}

CUSTOMER_CARE_USERNAME = "customer_care"
CUSTOMER_CARE_ADMIN_ID = 3042

_CATALOG = "menu_privilege"
_GRANTS = "menu_set_privilege"


def menu_privilege_catalog() -> list[dict]:
    """Active catalog rows merged with UI labels/descriptions."""
    rows = list_menu_privileges(active_only=True)
    by_perm = {str(r.get("permission") or ""): r for r in rows}
    out = []
    for key in MENU_PRIVILEGE_KEYS:
        meta = MENU_PRIVILEGE_META.get(key, {})
        row = by_perm.get(key) or {}
        out.append({
            "id": row.get("id"),
            "key": key,
            "menu_name": row.get("menu_name") or key,
            "permission": key,
            "label": meta.get("label", key),
            "description": meta.get("description", ""),
            "flag": int(row.get("flag") or 1),
        })
    return out


def all_menu_ids() -> list[str]:
    return list(MENU_PRIVILEGE_KEYS)


def all_menu_privileges(enabled: bool = True) -> dict:
    return {key: bool(enabled) for key in MENU_PRIVILEGE_KEYS}


def normalize_menu_ids(raw) -> list[str]:
    """Normalize to ordered unique known permission keys."""
    known = set(MENU_PRIVILEGE_KEYS)
    alias = {k.replace("_", "-"): k for k in MENU_PRIVILEGE_KEYS}
    selected: list[str] = []

    if isinstance(raw, dict):
        for key, value in raw.items():
            if not value:
                continue
            canon = alias.get(str(key), str(key))
            if canon in known and canon not in selected:
                selected.append(canon)
    elif isinstance(raw, (list, tuple, set)):
        for item in raw:
            canon = alias.get(str(item), str(item))
            if canon in known and canon not in selected:
                selected.append(canon)

    return [k for k in MENU_PRIVILEGE_KEYS if k in selected]


def menu_ids_to_privileges(menu_ids) -> dict:
    enabled = set(normalize_menu_ids(menu_ids))
    return {key: key in enabled for key in MENU_PRIVILEGE_KEYS}


def normalize_menu_privileges(raw, *, default: bool = False) -> dict:
    if isinstance(raw, (list, tuple, set)):
        return menu_ids_to_privileges(raw)
    out = all_menu_privileges(default)
    if isinstance(raw, dict):
        for key in MENU_PRIVILEGE_KEYS:
            if key in raw:
                out[key] = bool(raw[key])
            alt = key.replace("_", "-")
            if alt in raw:
                out[key] = bool(raw[alt])
    return out


def _now():
    return datetime.now(timezone.utc)


def ensure_menu_privilege_catalog() -> list[dict]:
    """Upsert the fixed menu_privilege seed rows. Idempotent."""
    if not use_mongodb():
        return []
    from .mongo import Repository

    repo = Repository(_CATALOG)
    now = _now()
    for mid, menu_name, permission in MENU_PRIVILEGE_SEED:
        existing = repo.find_one({"id": mid}) or repo.find_one({"permission": permission})
        # Rename legacy id=3 profit → profile if still present.
        if not existing and permission == "profile":
            legacy = repo.find_one({"permission": "profit"}) or repo.find_one({"id": 3})
            if legacy and str(legacy.get("permission") or "") == "profit":
                existing = legacy
        payload = {
            "id": mid,
            "menu_name": menu_name,
            "permission": permission,
            "flag": 1,
            "created_datetime": (existing or {}).get("created_datetime") or now,
        }
        if existing:
            repo.upsert({"id": existing.get("id", mid)}, payload)
        else:
            # Prefer stable seed id even if counter is ahead.
            try:
                repo.insert(payload)
            except Exception:
                repo.upsert({"permission": permission}, payload)
    # Soft-disable any leftover profit catalog row with a different id.
    for leftover in repo.find_all({"permission": "profit"}) or []:
        if int(leftover.get("id") or 0) != 3:
            repo.update({"id": leftover["id"]}, {"flag": 0})
    # Rename active grants that still point at legacy "profit".
    try:
        grants = Repository(_GRANTS)
        for g in grants.find_all({"privileges_name": "profit"}) or []:
            grants.update(
                {"id": g["id"]},
                {"privileges_name": "profile", "privileges_id": 3, "updatedOn": now},
            )
        for g in grants.find_all({"privileges_id": 3}) or []:
            if str(g.get("privileges_name") or "") == "profit":
                grants.update(
                    {"id": g["id"]},
                    {"privileges_name": "profile", "updatedOn": now},
                )
    except Exception:
        logger.debug("profit→profile grant rename skipped", exc_info=True)
    return list_menu_privileges(active_only=False)


def list_menu_privileges(*, active_only: bool = True) -> list[dict]:
    if not use_mongodb():
        return []
    from .mongo import Repository

    flt = {"flag": 1} if active_only else {}
    rows = Repository(_CATALOG).find_all(flt) or []
    rows.sort(key=lambda r: int(r.get("id") or 0))
    return [dict(r) for r in rows if r]


def get_menu_privilege_by_permission(permission: str) -> dict | None:
    key = str(permission or "").strip()
    if not key:
        return None
    if not use_mongodb():
        return None
    from .mongo import Repository

    row = Repository(_CATALOG).find_one({"permission": key, "flag": 1})
    if not row:
        # Hyphen alias
        alt = key.replace("-", "_")
        row = Repository(_CATALOG).find_one({"permission": alt, "flag": 1})
    return dict(row) if row else None


def get_menu_privilege_by_id(privileges_id: int) -> dict | None:
    try:
        pid = int(privileges_id)
    except (TypeError, ValueError):
        return None
    if not use_mongodb():
        return None
    from .mongo import Repository

    row = Repository(_CATALOG).find_one({"id": pid})
    return dict(row) if row else None


def list_user_grants(user_id: int, *, active_only: bool = True) -> list[dict]:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return []
    if not use_mongodb():
        return []
    from .mongo import Repository

    flt: dict = {"user_id": uid}
    if active_only:
        flt["flag"] = 1
    rows = Repository(_GRANTS).find_all(flt) or []
    return [dict(r) for r in rows if r]


def list_all_grants(*, active_only: bool = True) -> list[dict]:
    if not use_mongodb():
        return []
    from .mongo import Repository

    flt = {"flag": 1} if active_only else {}
    rows = Repository(_GRANTS).find_all(flt) or []
    return [dict(r) for r in rows if r]


def menu_ids_for_user(user_id: int) -> list[str]:
    grants = list_user_grants(user_id, active_only=True)
    names = [str(g.get("privileges_name") or "") for g in grants]
    return normalize_menu_ids(names)


def set_user_menu_privileges(user_id: int, menu_ids) -> list[dict]:
    """Replace active grants for ``user_id`` with the given menu permission keys.

    Soft-deletes (flag=0) removed menus; inserts/reactivates selected ones.
    """
    try:
        uid = int(user_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("user_id must be an integer") from exc
    if uid <= 0:
        raise ValueError("user_id must be a positive integer")

    ensure_menu_privilege_catalog()
    wanted = normalize_menu_ids(menu_ids)
    catalog = {str(r.get("permission")): r for r in list_menu_privileges(active_only=True)}
    wanted_ids = set()
    for key in wanted:
        row = catalog.get(key)
        if not row:
            continue
        wanted_ids.add(int(row["id"]))

    if not use_mongodb():
        raise RuntimeError("menu_set_privilege requires MongoDB")

    from .mongo import Repository

    repo = Repository(_GRANTS)
    now = _now()
    existing = list_user_grants(uid, active_only=False)
    by_priv: dict[int, dict] = {}
    for row in existing:
        try:
            by_priv[int(row["privileges_id"])] = row
        except (TypeError, ValueError, KeyError):
            continue

    # Soft-delete grants no longer selected
    for pid, row in by_priv.items():
        if pid not in wanted_ids and int(row.get("flag") or 0) == 1:
            repo.update(
                {"id": row["id"]},
                {"flag": 0, "updatedOn": now},
            )

    # Insert or reactivate selected grants
    for key in wanted:
        cat = catalog.get(key)
        if not cat:
            continue
        pid = int(cat["id"])
        name = str(cat.get("menu_name") or cat.get("permission") or key)
        prev = by_priv.get(pid)
        if prev:
            repo.update(
                {"id": prev["id"]},
                {
                    "flag": 1,
                    "privileges_name": name,
                    "updatedOn": now,
                    "user_id": uid,
                    "privileges_id": pid,
                },
            )
        else:
            repo.insert({
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "privileges_id": pid,
                "privileges_name": name,
                "createdOn": now,
                "updatedOn": now,
                "flag": 1,
            })

    return list_user_grants(uid, active_only=True)


def clear_user_menu_privileges(user_id: int) -> bool:
    """Soft-delete all grants for a user. Returns True if any were active."""
    grants = list_user_grants(user_id, active_only=True)
    if not grants:
        return False
    if not use_mongodb():
        return False
    from .mongo import Repository

    repo = Repository(_GRANTS)
    now = _now()
    for row in grants:
        repo.update({"id": row["id"]}, {"flag": 0, "updatedOn": now})
    return True


def is_superadmin_identity(
    *,
    username: str | None = None,
    role: str | None = None,
    admin_id: int | None = None,
) -> bool:
    """True for platform superadmin / customer_care — full menus, no DB grant check."""
    uname = str(username or "").strip().lower()
    if uname == CUSTOMER_CARE_USERNAME:
        return True
    if str(role or "").strip() == "super_admin":
        return True
    try:
        return int(admin_id or 0) == CUSTOMER_CARE_ADMIN_ID
    except (TypeError, ValueError):
        return False


def ensure_customer_care_privileges(
    *,
    username: str = CUSTOMER_CARE_USERNAME,
    admin_id: int | None = CUSTOMER_CARE_ADMIN_ID,
) -> list[dict]:
    """No-op for grants: superadmin never uses menu_set_privilege.

    Kept for import compatibility; only ensures the menu_privilege catalog exists.
    """
    del username, admin_id
    ensure_menu_privilege_catalog()
    return []


def effective_menu_privileges(
    *,
    username: str | None = None,
    role: str | None = None,
    admin_id: int | None = None,
    tenant_id: str | None = None,
) -> dict:
    """Resolve menu privileges for menu showing.

    - superadmin / customer_care → all True (no privilege API / DB lookup)
    - admin / sub_admin → menu_set_privilege by user_id (missing → all False)
    """
    del tenant_id
    if is_superadmin_identity(username=username, role=role, admin_id=admin_id):
        return all_menu_privileges(True)

    try:
        aid = int(admin_id) if admin_id is not None else 0
    except (TypeError, ValueError):
        aid = 0
    if not aid:
        return all_menu_privileges(False)
    try:
        return menu_ids_to_privileges(menu_ids_for_user(aid))
    except Exception:
        logger.debug("privilege lookup failed for user_id=%s", aid, exc_info=True)
        return all_menu_privileges(False)


# ── Back-compat aliases used by older imports / database.py re-exports ───────

def list_privileges() -> list[dict]:
    """Aggregate active grants grouped by user_id (for list API)."""
    ensure_menu_privilege_catalog()
    grants = list_all_grants(active_only=True)
    by_user: dict[int, dict] = {}
    for g in grants:
        try:
            uid = int(g.get("user_id"))
        except (TypeError, ValueError):
            continue
        bucket = by_user.setdefault(uid, {
            "user_id": uid,
            "menu_ids": [],
            "grants": [],
        })
        name = str(g.get("privileges_name") or "")
        if name and name not in bucket["menu_ids"]:
            bucket["menu_ids"].append(name)
        bucket["grants"].append(g)
    out = []
    for uid, bucket in sorted(by_user.items(), key=lambda x: x[0]):
        menu_ids = normalize_menu_ids(bucket["menu_ids"])
        out.append({
            "user_id": uid,
            "menu_ids": menu_ids,
            "privileges": menu_ids_to_privileges(menu_ids),
            "grants": bucket["grants"],
        })
    return out


def get_privilege_by_username(username: str) -> dict | None:
    """Resolve grants via admins.username → user_id (exact stored username)."""
    uname = str(username or "").strip()
    if not uname or not use_mongodb():
        return None
    from .admins import get_admin_by_username

    row = get_admin_by_username(uname)
    if not row:
        return None
    try:
        uid = int(row.get("id"))
    except (TypeError, ValueError):
        return None
    menu_ids = menu_ids_for_user(uid)
    return {
        "user_id": uid,
        "username": uname,
        "admin_id": uid,
        "menu_ids": menu_ids,
        "privileges": menu_ids_to_privileges(menu_ids),
    }


def get_privilege_by_admin_id(admin_id: int) -> dict | None:
    try:
        uid = int(admin_id)
    except (TypeError, ValueError):
        return None
    menu_ids = menu_ids_for_user(uid)
    return {
        "user_id": uid,
        "admin_id": uid,
        "menu_ids": menu_ids,
        "privileges": menu_ids_to_privileges(menu_ids),
    }


def upsert_privilege(username: str, menu_ids, *, admin_id: int | None = None) -> dict:
    """Assign menus to an admin (by admin_id / resolved username)."""
    uid = admin_id
    if uid is None:
        got = get_privilege_by_username(username)
        if not got:
            raise ValueError(f"admin not found for username={username!r}")
        uid = got["user_id"]
    grants = set_user_menu_privileges(int(uid), menu_ids)
    ids = normalize_menu_ids([g.get("privileges_name") for g in grants])
    return {
        "user_id": int(uid),
        "admin_id": int(uid),
        "username": str(username or "").strip() or None,
        "menu_ids": ids,
        "privileges": menu_ids_to_privileges(ids),
        "grants": grants,
    }


def delete_privilege(username: str) -> bool:
    got = get_privilege_by_username(username)
    if not got:
        return False
    return clear_user_menu_privileges(int(got["user_id"]))
