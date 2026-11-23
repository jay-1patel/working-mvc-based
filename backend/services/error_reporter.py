"""Central API / runtime error reporter (Backend Roadmap Phase 1).

Adapted from the `database` branch's error_reporter design (Nov 2026) to the
Phase-1 signature. Every unhandled API exception (wired in backend/main.py's
central handler) and any external-API failure (Send2, LLM, payments, uploads…)
should call :func:`report_error`. That:

1. Emits ONE greppable log line:
   ``API_ERROR | provider=… | api=… | req=… | tenant=… | …``
2. Persists a row in ``api_error_logs`` (created lazily; readable via
   ``POST /api/admin/errors``).
3. Optionally alerts — **OFF by default**. Alerting only happens when
   ``ERROR_ALERTS_ENABLED=1`` AND ``ALERT_WEBHOOK_URL`` is set; even then it is
   rate-limited so a stuck poller cannot spam. No WhatsApp sending here.

``report_error`` never raises: a reporter failure must never break the request
that was being reported.
"""

from __future__ import annotations

import logging
import re
import secrets
import os
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("error_reporter")

_lock = threading.Lock()
_last_alert_at: dict = {}


def redact_error(value) -> str:
    """Keep diagnostic text, never credentials or query-string values."""
    text = str(value or "")
    text = re.sub(r"(?i)(mongodb(?:\+srv)?://)[^\s/]+@", r"\1[REDACTED]@", text)
    text = re.sub(r"(?i)\bBearer\s+[^\s,;\"']+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)([\"']?(?:password|passwd|secret|token|api[_-]?key|authorization|otp|access_token|refresh_token)[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)", r"\1[REDACTED]", text)
    text = re.sub(r"(https?://[^\s?\"']+)\?[^\s\"']+", r"\1?[REDACTED]", text)
    return text




def _get_database():
    try:
        from db.mongo import get_database
    except ImportError:
        from backend.db.mongo import get_database
    return get_database()



def _alerts_enabled() -> bool:
    return (
        os.getenv("ERROR_ALERTS_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")
        and bool((os.getenv("ALERT_WEBHOOK_URL") or "").strip())
    )


def _cooldown_seconds() -> float:
    try:
        return float(os.getenv("ERROR_ALERT_COOLDOWN_SECONDS", "60"))
    except ValueError:
        return 60.0


def _should_notify(key: str) -> bool:
    now = time.monotonic()
    with _lock:
        last = _last_alert_at.get(key, 0.0)
        if now - last < _cooldown_seconds():
            return False
        _last_alert_at[key] = now
        return True


def _persist(*, provider, api, severity, message, detail, http_status,
             tenant_id, wa_id, request_id) -> bool:
    try:
        from pymongo import ReturnDocument
        database = _get_database()
        counter = database['_counters'].find_one_and_update({'_id':'api_error_logs'},
            {'$inc':{'seq':1}}, upsert=True, return_document=ReturnDocument.AFTER)
        database['api_error_logs'].insert_one({
            'id':counter['seq'], 'created_at':datetime.now(timezone.utc),
            'provider':(provider or 'unknown')[:80], 'api':(api or '')[:200],
            'severity':(severity or 'error')[:20], 'message':(message or '')[:500],
            'detail':(detail or '')[:4000], 'http_status':http_status,
            'tenant_id':tenant_id or None, 'wa_id':wa_id or None, 'request_id':request_id or None,
        })
        return True
    except Exception as exc:
        logger.warning('MongoDB error persistence failed: %s', type(exc).__name__)
        return False



def _push_webhook(text: str) -> None:
    """Best-effort webhook alert; only called when alerts are enabled."""
    try:
        url = (os.getenv("ALERT_WEBHOOK_URL") or "").strip()
        if not url:
            return
        req = urllib.request.Request(
            url,
            data=("{\"text\": " + _json_quote(text[:1500]) + "}").encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5).close()
    except Exception as exc:
        logger.debug("webhook alert failed: %s", exc)


def _json_quote(s: str) -> str:
    import json

    return json.dumps(s)


def report_error(
    provider: str,
    api: str,
    error,
    *,
    tenant_id: Optional[str] = None,
    request_id: Optional[str] = None,
    detail: Optional[str] = None,
    severity: str = "error",
    http_status: Optional[int] = None,
    wa_id: Optional[str] = None,
    notify: bool = True,
) -> bool:
    """Log + persist an API/runtime failure. Never raises.

    ``error`` may be a string message or an exception instance.
    """
    try:
        # Services and background tasks inherit request context when available.
        try:
            from core.context import request_id_var, error_tenant_var, error_context_var
        except ImportError:
            from backend.core.context import request_id_var, error_tenant_var, error_context_var
        request_id = request_id or request_id_var.get() or ("evt_" + secrets.token_hex(8))
        trace_context = error_context_var.get()
        context_tenant = (trace_context or {}).get("tenant_id") if trace_context is not None else None
        tenant_id = tenant_id or context_tenant or error_tenant_var.get()
        if isinstance(error, BaseException):
            message = str(error) or error.__class__.__name__
            if not detail:
                detail = "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )[-3500:]
        else:
            message = str(error or "")

        message = redact_error(message)
        detail = redact_error(detail)
        api = redact_error(api)

        line = (
            f"API_ERROR | provider={provider or 'unknown'} | api={api or '-'} "
            f"| req={request_id or '-'} | tenant={tenant_id or '-'} "
            f"| severity={severity} "
            f"| http={http_status if http_status is not None else '-'} "
            f"| {message[:300]}"
        )
        if severity == "warning":
            logger.warning(line)
        else:
            logger.error(line)

        persisted = _persist(
            provider=provider,
            api=api,
            severity=severity,
            message=message,
            detail=detail or "",
            http_status=http_status if http_status is not None else (500 if isinstance(error, BaseException) else None),
            tenant_id=tenant_id,
            wa_id=wa_id,
            request_id=request_id,
        )

        if not notify or not _alerts_enabled():
            return persisted
        key = f"{provider}|{api}|{severity}|{message[:80]}"
        if _should_notify(key):
            _push_webhook(f"[{severity.upper()}] {provider} {api}: {message[:300]}")
        return persisted
    except Exception as exc:  # absolute last line of defence
        logger.debug("report_error failed: %s", exc)
        return False


def report_exception(provider, api, exc, **kwargs) -> None:
    """Convenience wrapper mirroring the database-branch helper."""
    report_error(provider, api, exc, **kwargs)





def _error_filters(provider=None, tenant_id=None, search=None, severity=None,
                   http_status=None, since=None, until=None):
    filters = {}
    for key,value in (('provider',provider),('tenant_id',tenant_id),('severity',severity),('http_status',http_status)):
        if value is not None and value != '':
            filters[key] = value
    if search:
        filters['$or'] = [{key:{'$regex':re.escape(str(search)),'$options':'i'}} for key in ('message','api','request_id')]
    for operator,value in (('$gte',since),('$lte',until)):
        if value:
            date = datetime.fromisoformat(value.replace('Z','+00:00'))
            filters.setdefault('created_at',{})[operator] = date.replace(tzinfo=date.tzinfo or timezone.utc)
    return filters



def list_recent_errors(limit=50, provider=None, tenant_id=None, *, offset=0,
                       search=None, severity=None, http_status=None, since=None, until=None):
    filters = _error_filters(provider,tenant_id,search,severity,http_status,since,until)
    rows = _get_database()['api_error_logs'].find(filters,{'_id':0}).sort('id',-1).skip(max(0,int(offset))).limit(max(1,min(int(limit or 50),500)))
    return [_public_error(row) for row in rows]



def count_errors(**filters):
    return _get_database()['api_error_logs'].count_documents(_error_filters(**filters))

def _public_error(row):
    if row is not None and isinstance(row.get('created_at'),datetime):
        row['created_at'] = row['created_at'].isoformat()
    return row



class PersistentErrorHandler(logging.Handler):
    """Capture logged service failures, including caught background exceptions.

    Reporter records and central HTTP tracing are excluded to prevent loops and
    duplicate rows. Explicit provider events remain separate, linked by request ID.
    """
    def __init__(self):
        super().__init__(logging.WARNING)
        self._emitting = threading.local()

    def emit(self, record):
        if record.name == 'error_reporter' or getattr(self._emitting, 'busy', False):
            return
        try:
            message = record.getMessage()
        except Exception:
            return
        if message.startswith(('REQ ', 'API_FAIL |', 'ERROR_REPORT_FAILED |')):
            return
        self._emitting.busy = True
        try:
            try:
                from core.context import request_api_var
            except ImportError:
                from backend.core.context import request_api_var
            detail = ''.join(traceback.format_exception(*record.exc_info)) if record.exc_info else ''
            report_error(record.name, request_api_var.get() or record.name, message,
                         detail=detail, severity='error' if record.levelno >= logging.ERROR else 'warning', notify=False)
        except Exception:
            pass  # Logging must never break the service emitting the record.
        finally:
            self._emitting.busy = False


def get_error(error_id):
    return _public_error(_get_database()['api_error_logs'].find_one({'id':int(error_id)},{'_id':0}))
