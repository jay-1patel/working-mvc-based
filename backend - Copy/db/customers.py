"""Customer directory data access — extracted from backend/database.py."""
from datetime import datetime, timezone

from .core import logger, get_db_context, use_mongodb


def touch_customer(tenant_id, wa_id, name: str = "") -> None:
    """Create the customer on first contact, refresh them on every message.

    The live webhook calls this for EVERY inbound message — a plain "Hi" is
    enough to get a row — keyed on (tenant_id, wa_id) so nobody is duplicated.
    `name` is the WhatsApp profile name; it fills the record until something
    better (a lead form, an order) replaces it.
    """
    if not tenant_id or not wa_id:
        return
    now = datetime.utcnow().isoformat()
    try:
        if use_mongodb():
            from .mongo import Repository
            customers = Repository("customers")
            row = customers.find_one({"tenant_id": tenant_id, "wa_id": wa_id})
            if row is None:
                lang = ""
                try:
                    state_row = Repository("user_states").find_one({"wa_id": wa_id})
                    lang = (state_row.get("lang") if state_row else "") or ""
                except Exception:
                    logger.debug("CUSTOMER_LANG_LOOKUP_SKIPPED | wa=%s", wa_id, exc_info=True)
                customers.insert({
                    "tenant_id": tenant_id,
                    "wa_id": wa_id,
                    "name": (name or "").strip(),
                    "phone": wa_id,
                    "language": lang,
                    "message_count": 1,
                    "first_seen": now,
                    "last_seen": now,
                })
            else:
                new_name = (name or "").strip()
                old_name = row.get("name") or ""
                best = new_name if (new_name and (not old_name or old_name == wa_id)) else old_name
                customers.inc(
                    {"id": row["id"]},
                    "message_count",
                    1,
                    extra={"name": best, "last_seen": now},
                )
            return
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT id, name FROM customers WHERE tenant_id = ? AND wa_id = ?",
                (tenant_id, wa_id),
            ).fetchone()
            if row is None:
                lang = ""
                try:
                    state_row = conn.execute(
                        "SELECT lang FROM user_states WHERE wa_id = ?", (wa_id,)
                    ).fetchone()
                    lang = (state_row["lang"] if state_row else "") or ""
                except Exception:
                    # deliberate: language is a nice-to-have — the customer
                    # row is still touched without it.
                    logger.debug("CUSTOMER_LANG_LOOKUP_SKIPPED | wa=%s", wa_id, exc_info=True)
                # The WhatsApp id is the phone number in this system, so it
                # seeds the phone column; a volunteered number replaces it.
                conn.execute(
                    """INSERT INTO customers (tenant_id, wa_id, name, phone, language,
                       message_count, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (tenant_id, wa_id, (name or "").strip(), wa_id, lang, now, now),
                )
            else:
                new_name = (name or "").strip()
                old_name = row["name"] or ""
                best = new_name if (new_name and (not old_name or old_name == wa_id)) else old_name
                conn.execute(
                    "UPDATE customers SET name = ?, message_count = message_count + 1, "
                    "last_seen = ? WHERE id = ?",
                    (best, now, row["id"]),
                )
    except Exception as e:
        logger.warning(f"touch_customer failed for {wa_id}: {e}")


def update_customer_profile(tenant_id, wa_id, **fields) -> None:
    """Fill in profile fields a customer volunteered (lead flows, edits).

    Only non-empty values are written, so an update never blanks the record.
    """
    if not tenant_id or not wa_id:
        return
    allowed = ("name", "phone", "email", "city", "state", "company", "language")
    updates = {k: str(v).strip() for k, v in fields.items()
                if k in allowed and v and str(v).strip()}
    if not updates:
        return
    try:
        if use_mongodb():
            from .mongo import Repository
            Repository("customers").update(
                {"tenant_id": tenant_id, "wa_id": wa_id},
                updates,
            )
            return
        with get_db_context() as conn:
            sets = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE customers SET {sets} WHERE tenant_id = ? AND wa_id = ?",
                (*updates.values(), tenant_id, wa_id),
            )
    except Exception as e:
        logger.warning(f"update_customer_profile failed for {wa_id}: {e}")
