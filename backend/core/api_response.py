"""Uniform JSON API envelope: HTTP 200 always, success 1/0 in the body.

Logical HTTP semantics are preserved as ``code`` (e.g. 401, 404, 422) so
clients and logs can still distinguish failure kinds without relying on
the transport status line.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

from fastapi.responses import JSONResponse


SUCCESS = 1
FAILURE = 0


def success_payload(data: Optional[Mapping[str, Any]] = None, **extra: Any) -> dict:
    """Build a success body. Existing keys win over the injected flag only if
    the caller already set ``success``; otherwise ``success`` is forced to 1.

    Soft business results that use ``ok: false`` still get ``success: 1`` —
    the HTTP round-trip succeeded; callers read ``ok`` for the domain outcome.
    """
    body: dict = dict(data or {})
    body.update(extra)
    if "success" not in body:
        body["success"] = SUCCESS
    return body


def failure_payload(
    detail: Any,
    code: int,
    *,
    request_id: Optional[str] = None,
    api: Optional[str] = None,
    error: Optional[str] = None,
    **extra: Any,
) -> dict:
    """Build a failure body with success=0 and the logical HTTP ``code``."""
    err = error
    if err is None:
        err = detail if isinstance(detail, str) else f"HTTP {code}"
    body: dict = {
        "success": FAILURE,
        "code": int(code),
        "detail": detail,
        "error": err,
    }
    if request_id:
        body["request_id"] = request_id
    if api:
        body["api"] = api
    body.update(extra)
    return body


def json_ok(
    data: Optional[Mapping[str, Any]] = None,
    *,
    headers: Optional[Mapping[str, str]] = None,
    **extra: Any,
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=success_payload(data, **extra),
        headers=dict(headers or {}),
    )


def json_fail(
    detail: Any,
    code: int,
    *,
    request_id: Optional[str] = None,
    api: Optional[str] = None,
    error: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
    **extra: Any,
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=failure_payload(
            detail,
            code,
            request_id=request_id,
            api=api,
            error=error,
            **extra,
        ),
        headers=dict(headers or {}),
    )


def ensure_success_flag(payload: MutableMapping[str, Any], *, logical_code: int) -> MutableMapping[str, Any]:
    """Normalize an already-built JSON object to include success/code."""
    if logical_code >= 400:
        payload.setdefault("success", FAILURE)
        payload.setdefault("code", int(logical_code))
        if "error" not in payload and isinstance(payload.get("detail"), str):
            payload["error"] = payload["detail"]
        return payload
    if "success" not in payload:
        payload["success"] = SUCCESS
    return payload
