"""
Unified order service (Phase 2) — single create_order() for all personas.

Transaction (BEGIN IMMEDIATE) guarantees:
  1. Idempotency — same idempotency_key can never create two orders
     (partial unique index uq_orders_idempotency_key + explicit pre-check).
  2. Atomic confirm lock — checkout_sessions status transitions
     active → processing → confirmed via conditional UPDATE rowcount checks.
  3. No negative stock — conditional decrement
     (stock_quantity IS NULL = untracked → no check, per data-backfill reality).
  4. Cart cleared only after the order is committed.

Order numbers are sequential: ORD-<n> where n = max numeric suffix + 1.
"""
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger("order_service")


def _use_mongodb():
    from db.core import use_mongodb
    return use_mongodb()


def _gate(wa_id: str, feature: str = "orders"):
    """Refusal payload when this user's tenant has orders switched off.

    Same contract as cart_service._gate: returns None when allowed so the
    single-tenant deployment is unaffected.
    """
    import sys, os
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from shared.tenancy.gating import guard_result
    return guard_result(wa_id, feature)


def _db():
    import sys, os
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    import database as db
    return db


class OrderError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}")


def _next_order_number(conn) -> str:
    """Sequential ORD-<n> from the highest existing numeric suffix."""
    row = conn.execute(
        """SELECT MAX(CAST(SUBSTR(order_number, 5) AS INTEGER)) AS n
           FROM orders WHERE order_number GLOB 'ORD-[0-9]*'"""
    ).fetchone()
    n = (row["n"] or 0) + 1
    return f"ORD-{n}"


def _next_order_number_mongo(orders_repo, session=None) -> str:
    n = 0
    pattern = re.compile(r"^ORD-(\d+)$")
    for row in orders_repo.find_all({"order_number": {"$regex": r"^ORD-\d+$"}}, limit=None, session=session):
        match = pattern.match(str(row.get("order_number") or ""))
        if match:
            n = max(n, int(match.group(1)))
    return f"ORD-{n + 1}"


def _resolve_order_tenant(db, wa_id: str, tenant_id: str | None) -> str | None:
    tenant = (str(tenant_id or "").strip()) or None
    if not tenant:
        try:
            from shared.tenancy.resolver import resolve_tenant_for_user
            tenant = resolve_tenant_for_user(wa_id)
        except Exception:
            tenant = None
    if not tenant:
        try:
            tenant = db._resolve_tenant()
        except Exception:
            tenant = None
    return tenant


def _create_order_mongo(
    wa_id: str,
    items: list,
    total: float,
    source: str,
    session_id: str | None,
    idempotency_key: str | None,
    tier: str | None,
    discount_applied: float,
    tenant_id: str | None,
) -> dict:
    from db.mongo import Repository, get_database, transaction
    from db.core import unique_violation_error_types

    db = _db()
    tenant = _resolve_order_tenant(db, wa_id, tenant_id)
    database = get_database()
    duplicate_types = unique_violation_error_types()

    def _duplicate_response(orders_repo, session):
        if not idempotency_key:
            return None
        row = orders_repo.find_one({"idempotency_key": idempotency_key}, session=session)
        if not row:
            return None
        logger.info("ORDER_IDEMPOTENT_RACE | wa_id=%s | order=%s", wa_id, row["order_number"])
        return {
            "ok": True,
            "duplicate": True,
            "order_number": row["order_number"],
            "total": row["total_amount"],
        }

    def work(session):
        orders_repo = Repository("orders", database=database)
        products_repo = Repository("products", database=database)
        checkout_repo = Repository("checkout_sessions", database=database)
        carts_repo = Repository("carts", database=database)

        if idempotency_key:
            existing = orders_repo.find_one({"idempotency_key": idempotency_key}, session=session)
            if existing:
                logger.info(
                    "ORDER_IDEMPOTENT_HIT | wa_id=%s | order=%s",
                    wa_id, existing["order_number"],
                )
                return {
                    "ok": True,
                    "duplicate": True,
                    "order_number": existing["order_number"],
                    "total": existing["total_amount"],
                }

        if session_id:
            moved = checkout_repo.update(
                {"id": session_id, "status": "active"},
                {"status": "processing"},
                session=session,
            )
            if not moved:
                raise OrderError(
                    "session_not_active",
                    "checkout session already processed or expired",
                )

        for it in items:
            pid = it.get("product_id")
            if pid is None:
                continue
            prod = products_repo.find_one({"id": int(pid)}, session=session)
            if not prod:
                raise OrderError("out_of_stock", "Product is unavailable")
            stock = prod.get("stock_quantity")
            if stock is None:
                continue
            if int(stock) < it["qty"]:
                raise OrderError(
                    "out_of_stock",
                    f"{prod.get('name') or 'Product'} is unavailable",
                )
            decremented = products_repo.inc(
                {
                    "id": int(pid),
                    "stock_quantity": {"$gte": it["qty"]},
                },
                "stock_quantity",
                -it["qty"],
                session=session,
            )
            if not decremented:
                raise OrderError(
                    "out_of_stock",
                    f"{prod.get('name') or 'Product'} is unavailable",
                )

        order_number = _next_order_number_mongo(orders_repo, session=session)
        try:
            orders_repo.insert(
                {
                    "order_number": order_number,
                    "wa_id": wa_id,
                    "items": json.dumps(items),
                    "total_amount": total,
                    "status": "placed",
                    "payment_status": "pending",
                    "source": source,
                    "tier": tier,
                    "discount_applied": round(float(discount_applied or 0), 2),
                    "idempotency_key": idempotency_key,
                    "tenant_id": tenant,
                    "created_at": datetime.now(timezone.utc),
                },
                session=session,
            )
        except duplicate_types:
            dup = _duplicate_response(orders_repo, session)
            if dup:
                return dup
            raise OrderError("integrity", "order insert failed")

        if session_id:
            checkout_repo.update(
                {"id": session_id},
                {"status": "confirmed", "confirmed_order_number": order_number},
                session=session,
            )
        carts_repo.delete_many({"wa_id": wa_id}, session=session)
        logger.info(
            "ORDER_CREATED | wa_id=%s | order=%s | total=%s | source=%s",
            wa_id, order_number, total, source,
        )
        return {"ok": True, "duplicate": False, "order_number": order_number, "total": total}

    try:
        return transaction(work, database)
    except OrderError:
        raise
    except Exception as e:
        logger.error("ORDER_CREATE_FAIL | wa_id=%s | %s", wa_id, e)
        raise OrderError("internal", str(e))


def create_order(wa_id: str,
                 items: list,
                 source: str = "whatsapp",
                 session_id: str | None = None,
                 idempotency_key: str | None = None,
                 tier: str | None = None,
                 discount_applied: float = 0.0,
                 payment_method: str = "cod",
                 tenant_id: str | None = None) -> dict:
    """Create an order transactionally. Returns dict with order_number/total.

    Args:
        items: [{product_id, name, qty, price}] — price is the display/billed
               price already revalidated by the checkout engine.
        session_id: checkout_sessions row to confirm (status-lock + clear cart).
        idempotency_key: stored on the order; duplicates return the original.
    """
    db = _db()
    items = [
        {
            "product_id": it.get("product_id"),
            "name": it.get("name") or "Product",
            "qty": max(1, int(it.get("qty") or it.get("quantity") or 1)),
            "price": round(float(it.get("price") or 0), 2),
        }
        for it in (items or [])
    ]
    total = round(sum(i["qty"] * i["price"] for i in items) - float(discount_applied or 0), 2)

    if _use_mongodb():
        return _create_order_mongo(
            wa_id, items, total, source, session_id, idempotency_key,
            tier, discount_applied, tenant_id,
        )

    conn = db.get_db()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")

        # 1. Idempotency: honour an existing order for this key.
        if idempotency_key:
            existing = conn.execute(
                "SELECT order_number, total_amount FROM orders WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                conn.rollback()
                logger.info(f"ORDER_IDEMPOTENT_HIT | wa_id={wa_id} | order={existing['order_number']}")
                return {"ok": True, "duplicate": True,
                        "order_number": existing["order_number"],
                        "total": existing["total_amount"]}

        # 2. Atomic confirm lock on the checkout session.
        if session_id:
            cur = conn.execute(
                "UPDATE checkout_sessions SET status='processing' "
                "WHERE id = ? AND status = 'active'",
                (session_id,),
            )
            if cur.rowcount == 0:
                conn.rollback()
                raise OrderError("session_not_active",
                                 "checkout session already processed or expired")

        # 3. Conditional stock decrement (NULL stock = untracked).
        for it in items:
            pid = it.get("product_id")
            if pid is None:
                continue
            cur = conn.execute(
                "UPDATE products SET stock_quantity = stock_quantity - ? "
                "WHERE id = ? AND stock_quantity IS NOT NULL AND stock_quantity >= ?",
                (it["qty"], pid, it["qty"]),
            )
            if cur.rowcount == 0:
                # Not enough stock (or product vanished) — verify which.
                prod = conn.execute(
                    "SELECT name, stock_quantity FROM products WHERE id = ?", (pid,)
                ).fetchone()
                if prod and prod['stock_quantity'] is None:
                    continue  # untracked stock — always available
                conn.rollback()
                logger.info(
                    f"STOCK_DECREMENT_FAILED | product={pid} | "
                    f"stock={prod['stock_quantity'] if prod else 'gone'}"
                )
                raise OrderError("out_of_stock",
                                 f"{prod['name'] if prod else 'Product'} is unavailable")

        # 4. Insert order.
        # Tenancy: explicit arg wins, else the conversation's tenant from
        # user_states (stamped by the webhook), else the configured default.
        tenant = (str(tenant_id or "").strip()) or None
        if not tenant:
            try:
                from shared.tenancy.resolver import resolve_tenant_for_user
                tenant = resolve_tenant_for_user(wa_id)
            except Exception:
                tenant = None
        if not tenant:
            try:
                tenant = db._resolve_tenant()
            except Exception:
                tenant = None
        order_number = _next_order_number(conn)
        conn.execute(
            """INSERT INTO orders (order_number, wa_id, items, total_amount, status,
                                   payment_status, source, tier, discount_applied,
                                   idempotency_key, tenant_id)
               VALUES (?, ?, ?, ?, 'placed', 'pending', ?, ?, ?, ?, ?)""",
            (order_number, wa_id, json.dumps(items), total, source, tier,
             round(float(discount_applied or 0), 2), idempotency_key, tenant),
        )

        # 5. Confirm session + clear cart.
        if session_id:
            conn.execute(
                "UPDATE checkout_sessions SET status='confirmed', confirmed_order_number = ? "
                "WHERE id = ?",
                (order_number, session_id),
            )
        conn.execute(
            "DELETE FROM carts WHERE wa_id = ?", (wa_id,)
        )

        conn.commit()
        logger.info(f"ORDER_CREATED | wa_id={wa_id} | order={order_number} | total={total} | source={source}")
        return {"ok": True, "duplicate": False, "order_number": order_number, "total": total}

    except sqlite3.IntegrityError:
        # Concurrent insert raced us on idempotency_key — return the winner (SQLite only).
        conn.rollback()
        if idempotency_key:
            row = conn.execute(
                "SELECT order_number, total_amount FROM orders WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row:
                logger.info(f"ORDER_IDEMPOTENT_RACE | wa_id={wa_id} | order={row['order_number']}")
                return {"ok": True, "duplicate": True,
                        "order_number": row["order_number"], "total": row["total_amount"]}
        logger.error(f"ORDER_INTEGRITY_FAIL | wa_id={wa_id}")
        raise OrderError("integrity", "order insert failed")
    except OrderError:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"ORDER_CREATE_FAIL | wa_id={wa_id} | {e}")
        raise OrderError("internal", str(e))
    finally:
        conn.close()


def get_user_orders(wa_id: str, limit: int = 5) -> list:
    """Order tracking v1 — the user's most recent orders.

    Returns a refusal dict instead of a list when the user's tenant has the
    orders feature switched off, so a disabled feature reads as a normal turn
    rather than an exception. Callers must treat a dict as "blocked".
    """
    blocked = _gate(wa_id)
    if blocked:
        return blocked
    db = _db()
    try:
        if _use_mongodb():
            from db.mongo import Repository
            rows = Repository("orders").find(
                {"wa_id": wa_id},
                sort=[("created_at", -1), ("id", -1)],
                limit=limit,
            )
            return rows
        with db.get_db_context() as conn:
            rows = conn.execute(
                """SELECT order_number, items, total_amount, status, payment_status, created_at
                   FROM orders WHERE wa_id = ?
                   ORDER BY created_at DESC, id DESC LIMIT ?""",
                (wa_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"ORDER_LIST_FAIL | wa_id={wa_id} | {e}")
        return []


def format_orders_text(wa_id: str, limit: int = 5) -> str:
    blocked = _gate(wa_id)
    if blocked:
        return blocked["message"]
    orders = get_user_orders(wa_id, limit)
    if not orders:
        return "You have no orders yet. Browse the catalog to place your first order!"
    lines = ["*Your Recent Orders:*", ""]
    for o in orders:
        try:
            item_list = json.loads(o["items"] or "[]")
            summary = ", ".join(
                f"{i.get('name', 'Item')} ×{i.get('qty', 1)}" for i in item_list[:3]
            )
            if len(item_list) > 3:
                summary += f" +{len(item_list) - 3} more"
        except Exception:
            summary = "items"
        lines.append(
            f"• {o['order_number']} — {o['status']} — ₹{o['total_amount']:.2f}\n  {summary}"
        )
    return "\n".join(lines)


def lookup_order_status(wa_id: str, order_ref: str) -> str:
    """Look up one order by number (scoped to this WhatsApp user) + shipment info."""
    blocked = _gate(wa_id)
    if blocked:
        return blocked["message"]
    ref = (order_ref or "").strip()
    if not ref:
        return format_orders_text(wa_id)

    db = _db()
    try:
        if _use_mongodb():
            from db.mongo import Repository
            orders = Repository("orders")
            row = orders.find_one({"wa_id": wa_id, "order_number": ref})
            if not row and ref.isdigit():
                row = orders.find_one({"wa_id": wa_id, "id": int(ref)})
        else:
            with db.get_db_context() as conn:
                row = conn.execute(
                    """SELECT id, order_number, items, total_amount, status, payment_status,
                              created_at, tenant_id
                       FROM orders
                       WHERE wa_id = ? AND (order_number = ? OR CAST(id AS TEXT) = ?)
                       LIMIT 1""",
                    (wa_id, ref, ref),
                ).fetchone()
                row = dict(row) if row else None
        if not row:
            recent = format_orders_text(wa_id, limit=3)
            return (
                f"I couldn't find order *{ref}* on this number.\n\n{recent}"
            )

        try:
            item_list = json.loads(row["items"] or "[]")
            summary = ", ".join(
                f"{i.get('name', 'Item')} ×{i.get('qty', 1)}" for i in item_list[:5]
            ) or "items"
        except Exception:
            summary = "items"

        lines = [
            f"📦 *Order {row['order_number']}*",
            f"Status: *{row['status']}*",
            f"Payment: *{row['payment_status'] or 'pending'}*",
            f"Total: ₹{float(row['total_amount'] or 0):.2f}",
            f"Items: {summary}",
            f"Placed: {row['created_at']}",
        ]

        if _use_mongodb():
            from db.mongo import Repository
            ships = Repository("tenant_shipments").find(
                {
                    "$or": [
                        {"order_id": row["order_number"]},
                        {"order_id": str(row["id"])},
                    ]
                },
                sort=[("id", -1)],
                limit=1,
            )
            ship = ships[0] if ships else None
        else:
            with db.get_db_context() as conn:
                ship = conn.execute(
                    """SELECT awb_number, tracking_url, status, provider
                       FROM tenant_shipments
                       WHERE order_id = ? OR order_id = ?
                       ORDER BY id DESC LIMIT 1""",
                    (row["order_number"], str(row["id"])),
                ).fetchone()
                ship = dict(ship) if ship else None
        if ship:
            lines.append("")
            lines.append(
                f"🚚 Shipment ({ship['provider'] or 'carrier'}): "
                f"*{ship['status'] or 'booked'}*"
            )
            if ship.get("awb_number"):
                lines.append(f"AWB: {ship['awb_number']}")
            if ship.get("tracking_url"):
                lines.append(f"Track: {ship['tracking_url']}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"ORDER_LOOKUP_FAIL | wa_id={wa_id} | ref={ref} | {e}")
        return "Sorry, I couldn't look that order up right now. Please try again shortly."
