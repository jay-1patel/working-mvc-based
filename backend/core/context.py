"""Request-scoped context shared by the app and the logging setup.

Phase 1 introduced the request-id context variable inside the main app
module; Phase 2 moves the variable itself here so the single logging setup
(``core.logging``) can read it without importing the app module (which would
be a circular import). The app middleware and the handlers keep using the
exact same variable object — behavior is unchanged.
"""
from contextvars import ContextVar

#: The current request's id (``req_<8 hex>``), or "" outside a request.
request_id_var: ContextVar = ContextVar("request_id", default="")
request_api_var: ContextVar = ContextVar("request_api", default="")
error_tenant_var: ContextVar = ContextVar("error_tenant", default=None)
# A shared request dictionary lets sync authentication dependencies annotate
# context inherited by worker threads without leaking it into other requests.
error_context_var: ContextVar = ContextVar("error_context", default=None)


def get_request_id() -> str:
    """Return the current request id, or "" when not handling a request."""
    return request_id_var.get()
