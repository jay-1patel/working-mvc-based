# Tracing failures in AI Chatbot

Open **Errors & health** as a super admin (all tenants) or company admin (own
tenant). Sub-admins can send browser diagnostics but cannot read error logs.

The page refreshes every 15 seconds while visible. Search by request ID, API,
or message; narrow by source, tenant, severity, status, and dates. Use Previous /
Next to reach older events. Download page exports the currently loaded records.
Expand **Trace details** for stack traces or validation field names.

## What is captured

- Every HTTP response with a status of 400 or higher that passes through the
  application request middleware, including handled failures and validation.
- Unhandled server exceptions with stack traces and a request ID returned in
  `X-Request-Id` and the error response. A request failure is recorded once;
  distinct service failures can share the same ID.
- `logger.error`, `logger.exception`, and `logger.warning` (including recoverable provider failures)
  after the central logging setup runs. Background events get an `evt_` ID;
  events within a request inherit its ID and available tenant context.
- Explicit `report_error(...)` calls for provider/service failures.
- Signed-in browser runtime errors, rejected promises, React rendering errors,
  and transport failures from the shared API client. They carry `client_` IDs;
  trace details include the original browser event time and page.

The browser retries at most 50 queued events in memory after connectivity
returns, every 30 seconds or on an online event. Closing/reloading the tab loses
undelivered events. Queued events are never attributed to a different account.
The ingestion endpoint is authenticated and limits each account to 30 events
per minute. Reports rejected for rate limiting are dropped.

## Trace a problem

1. Copy the request/error ID from the UI error or browser Network response.
2. Paste it into **Search logs**, then click **Apply filters**.
3. Compare related API and service events, timestamps, and expanded details.
4. Share the ID and downloaded page with the developer investigating the cause.

Passwords, bearer tokens, API keys, OTPs, and URL query values are redacted from
persisted diagnostic text. Request bodies and headers are not captured by this
error logger. Validation logs contain field names/types/messages, not inputs.

## Practical limits

This is an application error log, not an uptime monitor. A stopped process or
unavailable database cannot reliably persist its own failure; console/service
logs are still needed. Errors silently swallowed without logging/reporting,
and failures before the browser application loads, cannot be captured here.
The logger does not manufacture a healthy status from an empty error list.

The focused backend tests use temporary databases and synthetic failures;
they never trigger real provider sends or damage live data.
