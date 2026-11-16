"""
State manager with optimistic locking for cross-worker safety.

Read-modify-write on user_states.context_json with version-based
optimistic concurrency control. Safe for SQLite WAL mode.

Phase 0.3 (decision D3): conversation state EXTENDS this module rather than
adding a parallel table. One state owner, one version column, one lock.

    user_states.tenant_id     which brand this conversation belongs to
    user_states.active_flow   flow name currently running (NULL = none)
    user_states.current_step  step id inside that flow
    user_states.collected     TEXT holding the flow's collected data as JSON
    user_states.status        bot | paused | handoff

handoff expiry stays owned by services/handoff_timeout.py — the flow runner
only sets and resets `status`.
"""
import json
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger("state_manager")

_SQLITE_DISABLED = (
    "user_states access requires MongoDB; SQLite get_db_context is disabled"
)


def _use_mongodb():
    from db.core import use_mongodb
    return use_mongodb()


def _states_repo():
    from db.mongo import Repository
    return Repository("user_states")

B2C_CHECKOUT_STATES = [
    "B2C_CHECKOUT_NAME", "B2C_CHECKOUT_MOBILE", "B2C_CHECKOUT_PINCODE",
    "B2C_CHECKOUT_ADDRESS", "B2C_CHECKOUT_PAYMENT", "B2C_CHECKOUT_FINAL_CONFIRM",
    "B2C_CHECKOUT_CONFIRM", "B2C_AWAITING_QTY", "B2C_BROWSING_PRODUCTS",
    "B2C_VIEWING_PRODUCT", "B2C_VIEWING_CART",
]

B2B_CHECKOUT_STATES = [
    "DIST_ASK_NAME", "DIST_ASK_MOBILE", "DIST_ASK_ADDRESS",
    "DIST_REVIEW_ORDER", "DIST_BROWSE_PRODUCTS",
]

ALL_CHECKOUT_STATES = B2C_CHECKOUT_STATES + B2B_CHECKOUT_STATES

# ── conversation status values ────────────────────────────────────────────
STATUS_BOT = "bot"
STATUS_PAUSED = "paused"
STATUS_HANDOFF = "handoff"
VALID_STATUSES = (STATUS_BOT, STATUS_PAUSED, STATUS_HANDOFF)

FLOW_COLUMNS = "tenant_id, active_flow, current_step, collected, status"



class OptimisticLockError(Exception):
    pass


def get_user_state(wa_id: str) -> str | None:
    """Return current state string, or None if no record."""
    try:
        if _use_mongodb():
            row = _states_repo().find_one({"wa_id": wa_id})
            return row.get("state") if row else None
        raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"get_user_state failed for {wa_id}: {e}")
        return None


def read_user_context(wa_id: str) -> tuple[dict, int]:
    """Return (context_dict, version). Empty dict + 0 if no record."""
    try:
        if _use_mongodb():
            row = _states_repo().find_one({"wa_id": wa_id})
            if not row:
                return {}, 0
            ctx = row.get("context_json")
            if isinstance(ctx, str):
                ctx = json.loads(ctx or "{}")
            elif not isinstance(ctx, dict):
                ctx = {}
            return ctx, int(row.get("version") or 0)
        raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"read_user_context failed for {wa_id}: {e}")
        return {}, 0


def write_user_context(wa_id: str, context: dict, expected_version: int) -> bool:
    """CAS write: update only if version matches. Returns True on success."""
    try:
        if _use_mongodb():
            repo = _states_repo()
            updated = repo.inc(
                {"wa_id": wa_id, "version": expected_version},
                "version",
                1,
                extra={
                    "context_json": context,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            return updated > 0
        raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"write_user_context failed for {wa_id}: {e}")
        return False


def update_context_with_retry(
    wa_id: str, update_fn, max_retries: int = 3
) -> dict:
    """
    Read-modify-write with optimistic-lock retry.

    update_fn MUST BE PURE: mutate the dict only. No WhatsApp sends,
    no DB writes, no HTTP — retries re-execute it.
    """
    for attempt in range(max_retries):
        context, version = read_user_context(wa_id)
        update_fn(context)
        if write_user_context(wa_id, context, expected_version=version):
            return context
        if attempt < max_retries - 1:
            time.sleep(0.05 * (attempt + 1))
            logger.debug(f"Lock retry {attempt + 1} for {wa_id}")
    raise OptimisticLockError(
        f"Context update failed after {max_retries} retries: {wa_id}"
    )


def save_context(wa_id: str, context: dict) -> bool:
    """Full-context write with retry. Returns False on persistent failure."""
    try:
        def apply(ctx):
            ctx.clear()
            ctx.update(context)
        update_context_with_retry(wa_id, apply)
        return True
    except OptimisticLockError:
        logger.error(f"save_context: lock failed after retries for {wa_id}")
        return False
    except Exception as e:
        logger.error(f"save_context error for {wa_id}: {e}")
        return False


def check_state_expiry(wa_id: str, context: dict, checkout_states: list,
                       state_ttl: dict) -> dict:
    """
    TTL check + retry-safe state reset.
    Returns {'expired': bool, 'message': str|None, 'context': dict}.
    """
    current_state = context.get("state")
    last_activity = context.get("last_activity_at", 0)

    if not current_state or current_state not in state_ttl:
        context["last_activity_at"] = time.time()
        return {"expired": False, "message": None, "context": context}

    if time.time() - last_activity <= state_ttl[current_state]:
        context["last_activity_at"] = time.time()
        return {"expired": False, "message": None, "context": context}

    # State expired — try to reset with retry
    has_cart = bool(context.get("cart", {}).get("items"))
    has_draft = bool(context.get("order_draft") or context.get("browsing_product_id"))

    if has_cart or has_draft:
        msg = ("⏰ Session timed out.\n\n"
               "Reply:\n• *resume* — Continue where you left off\n"
               "• *menu* — Start over")
    else:
        msg = "⏰ Session timed out. Reply *menu* to start over."

    target_state = "B2C_AWAITING_MAIN_SELECTION" if current_state.startswith("B2C_") else "B2B_MAIN_MENU"

    def reset(ctx):
        ctx["state"] = target_state
        ctx["last_activity_at"] = time.time()
        if has_cart:
            ctx["pending_checkout_expired"] = current_state
        elif has_draft:
            ctx["pending_b2b_expired"] = current_state

    try:
        final_ctx = update_context_with_retry(wa_id, reset)
        context.update(final_ctx)
    except OptimisticLockError:
        logger.error(f"State expiry reset failed for {wa_id}")

    return {"expired": True, "message": msg, "context": context}


# -- Flow / conversation state (Phase 0.3, decision D3) -------------------
# Same table, same version column, same CAS write. Flows get no parallel store.

def _loads_collected(raw) -> dict:
    if not raw:
        return {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _resolve_state_tenant(wa_id: str, tenant_id: str | None = None) -> str | None:
    """Which tenant a conversation row for ``wa_id`` belongs to.

    Resolution order:
      1. the tenant passed in by the caller — the tenant this message is
         actually being handled for (flow runner / orchestrator context),
      2. the current request tenant, set by the orchestrator/webhook at the
         start of message handling,
      3. the tenant that already owns this user,
      4. the bot's default tenant resolution (active test tenant /
         DEFAULT_TENANT_ID / the single active tenant).

    Returns None when no tenant can be determined. Callers must log and
    skip the write — never invent a tenant.
    """
    if tenant_id:
        return str(tenant_id)
    try:
        from database import get_request_tenant
        request_tenant = get_request_tenant()
        if request_tenant:
            return str(request_tenant)
    except Exception:
        # deliberate: resolver chain — fall through to the next source.
        logger.debug("STATE_TENANT_RESOLVE_STEP_SKIPPED | source=request_context", exc_info=True)
    try:
        from shared.tenancy.resolver import resolve_tenant_for_user
        owner = resolve_tenant_for_user(wa_id)
        if owner:
            return str(owner)
    except Exception:
        # deliberate: resolver chain — fall through to the next source.
        logger.debug("STATE_TENANT_RESOLVE_STEP_SKIPPED | source=user_owner wa=%s", wa_id, exc_info=True)
    try:
        from shared.tenancy.resolver import resolve_default_tenant
        return resolve_default_tenant()
    except Exception:
        return None


def ensure_conversation_row(wa_id: str, tenant_id: str | None = None) -> None:
    """Create the user_states row if missing, so flow state always has a home.

    Idempotent and cheap. Without this a brand-new number would silently fail
    every flow write.
    """
    t_id = _resolve_state_tenant(wa_id, tenant_id)
    if not t_id:
        logger.error(
            f"ensure_conversation_row skipped for {wa_id}: no tenant could be "
            "resolved (none passed in, no request tenant, user unowned, no default)"
        )
        return
    try:
        if _use_mongodb():
            repo = _states_repo()
            if not repo.find_one({"tenant_id": t_id, "wa_id": wa_id}):
                repo.insert({
                    "tenant_id": t_id,
                    "wa_id": wa_id,
                    "state": "B2C_MAIN_MENU",
                    "context_json": {},
                    "collected": {},
                    "status": STATUS_BOT,
                    "version": 0,
                })
        else:
            raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"ensure_conversation_row failed for {wa_id}: {e}")


def read_conversation(wa_id: str) -> dict:
    """Full conversation row: state, context, tenant, flow progress, status."""
    try:
        if _use_mongodb():
            row = _states_repo().find_one({"wa_id": wa_id})
            if row is None:
                ensure_conversation_row(wa_id)
                return {
                    "wa_id": wa_id,
                    "state": "MAIN_MENU",
                    "context": {},
                    "version": 0,
                    "tenant_id": None,
                    "active_flow": None,
                    "current_step": None,
                    "collected": {},
                    "status": STATUS_BOT,
                }
            try:
                context = row.get("context_json")
                if isinstance(context, str):
                    context = json.loads(context or "{}")
                elif not isinstance(context, dict):
                    context = {}
            except (json.JSONDecodeError, TypeError):
                context = {}
            return {
                "wa_id": wa_id,
                "state": row.get("state"),
                "context": context,
                "version": int(row.get("version") or 0),
                "tenant_id": row.get("tenant_id"),
                "active_flow": row.get("active_flow"),
                "current_step": row.get("current_step"),
                "collected": _loads_collected(row.get("collected")),
                "status": row.get("status") or STATUS_BOT,
            }
        raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"read_conversation failed for {wa_id}: {e}")
        return {}



def active_flow(wa_id: str) -> str | None:
    """Name of the flow currently running for this user, or None."""
    try:
        if _use_mongodb():
            row = _states_repo().find_one({"wa_id": wa_id})
            return (row.get("active_flow") if row else None) or None
        raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"active_flow failed for {wa_id}: {e}")
        return None


def get_status(wa_id: str) -> str:
    try:
        if _use_mongodb():
            row = _states_repo().find_one({"wa_id": wa_id})
            return (row.get("status") if row else None) or STATUS_BOT
        raise RuntimeError(_SQLITE_DISABLED)
    except Exception as e:
        logger.error(f"get_status failed for {wa_id}: {e}")
        return STATUS_BOT


def update_conversation_with_retry(wa_id: str, mutate, max_retries: int = 3) -> dict:
    """Read-modify-write the conversation row under the same optimistic lock.

    ``mutate`` MUST BE PURE � it receives the conversation dict and mutates it
    in place. Retries re-execute it, so no sends, no HTTP, no nested writes.
    """
    for attempt in range(max_retries):
        convo = read_conversation(wa_id)
        if not convo:
            logger.warning(f"update_conversation_with_retry: no user_states row for {wa_id}")
            return {}
        mutate(convo)
        tid = convo.get("tenant_id")
        if not tid:
            tid = _resolve_state_tenant(wa_id)
        if not tid:
            logger.error(
                f"conversation write skipped for {wa_id}: no tenant could be resolved"
            )
            return {}
        try:
            if _use_mongodb():
                repo = _states_repo()
                updated = repo.inc(
                    {"wa_id": wa_id, "version": convo.get("version", 0)},
                    "version",
                    1,
                    extra={
                        "tenant_id": tid,
                        "active_flow": convo.get("active_flow"),
                        "current_step": convo.get("current_step"),
                        "collected": convo.get("collected") or {},
                        "status": convo.get("status") or STATUS_BOT,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
                if updated > 0:
                    return convo
            else:
                raise RuntimeError(_SQLITE_DISABLED)
        except Exception as e:
            logger.error(f"conversation write failed for {wa_id}: {e}")
            return {}
        if attempt < max_retries - 1:
            time.sleep(0.05 * (attempt + 1))
    logger.error(f"conversation update lost the lock after {max_retries} retries: {wa_id}")
    return {}


def set_tenant(wa_id: str, tenant_id: str) -> bool:
    def mutate(c):
        c["tenant_id"] = str(tenant_id)
    return bool(update_conversation_with_retry(wa_id, mutate))


def start_flow(wa_id: str, flow_name: str, step_id: str = "") -> bool:
    """Begin a flow. Clears any previous flow's collected data."""
    def mutate(c):
        c["active_flow"] = str(flow_name)
        c["current_step"] = str(step_id or "")
        c["collected"] = {}
        c["status"] = STATUS_BOT
    return bool(update_conversation_with_retry(wa_id, mutate))


def set_step(wa_id: str, step_id: str) -> bool:
    def mutate(c):
        c["current_step"] = str(step_id)
    return bool(update_conversation_with_retry(wa_id, mutate))


def set_collected(wa_id: str, key: str, value) -> bool:
    def mutate(c):
        c.setdefault("collected", {})[str(key)] = value
    return bool(update_conversation_with_retry(wa_id, mutate))


def merge_collected(wa_id: str, values: dict) -> bool:
    if not values:
        return True
    def mutate(c):
        c.setdefault("collected", {}).update(values)
    return bool(update_conversation_with_retry(wa_id, mutate))


def set_status(wa_id: str, status: str) -> bool:
    """Set bot | paused | handoff. handoff_timeout.py still owns expiry."""
    if status not in VALID_STATUSES:
        logger.warning(f"Ignoring invalid status {status!r} for {wa_id}")
        return False
    def mutate(c):
        c["status"] = status
    return bool(update_conversation_with_retry(wa_id, mutate))


def clear_flow(wa_id: str, *, reset_status: bool = True) -> bool:
    """End the running flow and drop its collected data."""
    def mutate(c):
        c["active_flow"] = None
        c["current_step"] = None
        c["collected"] = {}
        if reset_status:
            c["status"] = STATUS_BOT
    return bool(update_conversation_with_retry(wa_id, mutate))
