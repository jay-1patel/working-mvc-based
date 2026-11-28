/**
 * Single fetch wrapper for the whole app.
 *
 * Authentication is ``username`` + ``session_id`` only:
 *   - headers ``username`` + ``session_id``
 *   - the same fields on JSON / multipart bodies
 *
 * ``user_id`` may be cached for display; it is never sent for auth.
 *
 * Backend JSON APIs always return HTTP 200. Success/failure is in the body:
 *   ``success: 1`` ok, ``success: 0`` failure (logical status in ``code``).
 * Failures are normalised into an `ApiError` carrying the server's `detail`.
 */

import { captureClientError } from './client-errors'

const TOKEN_KEY = 'tenant-console.token'
const USER_ID_KEY = 'tenant-console.user_id'
const USERNAME_KEY = 'tenant-console.username'
const SESSION_KEY = 'tenant-console.session_id'
const TENANT_KEY = 'tenant-console.tenant'

/**
 * Leave empty when the frontend and API share an origin. Set
 * VITE_API_ORIGIN (for example https://api.example.com) when this console is
 * hosted separately; every API call below is then forwarded to that origin.
 */
const API_ORIGIN = (import.meta.env.VITE_API_ORIGIN as string | undefined)?.replace(/\/$/, '') ?? ''

export function apiUrl(path: string): string {
  if (!API_ORIGIN || /^(?:https?:)?\/\//i.test(path)) return path
  return `${API_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`
}

export class ApiError extends Error {
  status: number
  requestId?: string
  constructor(status: number, message: string, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.requestId = requestId
  }
}

/* ------------------------------------------------------------------ */
/* Console tracing — one line per API call, so any error can be       */
/* traced to its exact method + path + status in DevTools. On by      */
/* default; switch off with localStorage DEBUG_API = '0'.             */
/* ------------------------------------------------------------------ */

/** True unless the user opted out via localStorage DEBUG_API='0'. Never throws. */
export function apiLoggingEnabled(): boolean {
  try {
    return localStorage.getItem('DEBUG_API') !== '0'
  } catch {
    return true
  }
}

function timerNow(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

/** Start stamp for timing a raw-fetch API call (uploads, exports, …). */
export function apiCallStart(): number {
  return timerNow()
}

function elapsedMs(startedAt: number): number {
  return Math.max(0, Math.round(timerNow() - startedAt))
}

/** Log a completed API call: `[api] GET /api/tenants → 200 (84ms)`. */
export function logApiCall(method: string, path: string, status: number, startedAt: number): void {
  if (!apiLoggingEnabled()) return
  console.log(`[api] ${method} ${path} → ${status} (${elapsedMs(startedAt)}ms)`)
}

/** Log a failed API call with the server's error detail, via console.error.
 * When the backend sent a request_id, it is appended as `(error id: req_…)`
 * so the line can be matched to exactly one backend log line / error row. */
export function logApiError(
  method: string,
  path: string,
  status: number,
  detail: string,
  startedAt: number,
  requestId?: string | null,
): void {
  if (!apiLoggingEnabled()) return
  const idPart = requestId ? ` (error id: ${requestId})` : ''
  console.error(`[api] ${method} ${path} → ${status} (${elapsedMs(startedAt)}ms) — ${detail}${idPart}`)
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getUserId(): string | null {
  try {
    return localStorage.getItem(USER_ID_KEY)
  } catch {
    return null
  }
}

/** Plain login username used for API auth with session_id. */
export function getUsername(): string | null {
  try {
    return localStorage.getItem(USERNAME_KEY)
  } catch {
    return null
  }
}

export function getSessionId(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

/**
 * Persist session credentials. Auth uses plain ``username`` + ``sessionId``.
 * ``userId`` is stored for display / dropdowns only.
 */
export function setCredentials(
  userId: string | number,
  sessionId: string,
  username?: string | null,
) {
  const id = String(userId).trim()
  const session = sessionId.trim()
  const plain = username != null ? String(username).trim() : ''
  const token = btoa(`${plain || id}:${session}`)
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_ID_KEY, id)
    localStorage.setItem(SESSION_KEY, session)
    if (plain) {
      localStorage.setItem(USERNAME_KEY, plain)
    }
  } catch {
    /* private mode — the session simply does not persist */
  }
}

export function setToken(token: string | null) {
  try {
    if (!token) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_ID_KEY)
      localStorage.removeItem(USERNAME_KEY)
      localStorage.removeItem(SESSION_KEY)
      return
    }
    localStorage.setItem(TOKEN_KEY, token)
    try {
      const decoded = atob(token)
      const idx = decoded.indexOf(':')
      if (idx > 0) {
        const left = decoded.slice(0, idx)
        const right = decoded.slice(idx + 1)
        localStorage.setItem(SESSION_KEY, right)
        if (/^\d+$/.test(left)) {
          localStorage.setItem(USER_ID_KEY, left)
        } else {
          // Legacy token username:session_id — keep username; user_id comes from /me later.
          localStorage.setItem(USERNAME_KEY, left)
        }
      }
    } catch {
      /* keep whatever keys already exist */
    }
  } catch {
    /* private mode — the session simply does not persist */
  }
}

/** Auth headers — username + session_id (no Authorization). */
export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const username = getUsername()
  const sessionId = getSessionId()
  if (username) headers.username = username
  if (sessionId) headers.session_id = sessionId
  return headers
}

/** Attach username + session_id on every JSON body (does not overwrite payload keys). */
function withSessionBody(body: unknown): unknown {
  const username = getUsername()
  const sessionId = getSessionId()
  if ((!username && !sessionId) || body === undefined || body === null) return body
  if (typeof body === 'object' && !Array.isArray(body)) {
    const payload = body as Record<string, unknown>
    return {
      ...payload,
      ...(username && payload.username == null ? { username } : {}),
      ...(sessionId && payload.session_id == null ? { session_id: sessionId } : {}),
    }
  }
  return body
}

export function getActiveTenantId(): string | null {
  try {
    return localStorage.getItem(TENANT_KEY)
  } catch {
    return null
  }
}

export function setActiveTenantId(tenantId: string | null) {
  try {
    if (tenantId) localStorage.setItem(TENANT_KEY, tenantId)
    else localStorage.removeItem(TENANT_KEY)
  } catch {
    /* ignore */
  }
}

type Unauthorized = () => void

let onUnauthorized: Unauthorized = () => {}

export function setUnauthorizedHandler(fn: Unauthorized) {
  onUnauthorized = fn
}

/** True when the envelope marks the call as failed (success 0/false). */
export function isEnvelopeFailure(body: unknown): boolean {
  if (!body || typeof body !== 'object') return false
  const success = (body as { success?: unknown }).success
  return success === 0 || success === false || success === '0'
}

/** Logical HTTP code from body ``code`` or ``X-Api-Code``, else transport status. */
export function logicalStatus(res: Response, body: unknown): number {
  if (body && typeof body === 'object') {
    const code = (body as { code?: unknown }).code
    if (typeof code === 'number' && Number.isFinite(code)) return code
    if (typeof code === 'string' && /^\d+$/.test(code)) return Number(code)
  }
  const headerCode = res.headers?.get?.('X-Api-Code')
  if (headerCode && /^\d+$/.test(headerCode)) return Number(headerCode)
  return res.status
}

/** True when transport failed or the JSON envelope reports success=0. */
export function isApiFailure(res: Response, body: unknown): boolean {
  return !res.ok || isEnvelopeFailure(body)
}

/**
 * For blob/file downloads: if the server returned a JSON error envelope
 * (always HTTP 200 now) or a non-OK transport status, throw ApiError.
 * Otherwise return null so the caller can read the blob.
 */
export async function rejectIfApiJsonError(
  res: Response,
  fallbackDetail: string,
): Promise<{ detail: string; code: number } | null> {
  const contentType = (res.headers.get('content-type') || '').toLowerCase()
  const looksJson = contentType.includes('application/json')
  if (!looksJson && res.ok) return null
  if (!looksJson && !res.ok) {
    return { detail: fallbackDetail, code: res.status }
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    if (!res.ok) return { detail: fallbackDetail, code: res.status }
    return null
  }
  if (!isApiFailure(res, body)) return null
  const info = errorInfoFromBody(res, body)
  return { detail: info.detail || fallbackDetail, code: info.code }
}

/** Detail text plus the backend request_id (body field first, then the
 * X-Request-Id header the Phase-1 middleware stamps on every response). */
function errorInfoFromBody(
  res: Response,
  body: unknown,
): { detail: string; requestId: string | null; code: number } {
  const headerId = res.headers?.get?.('X-Request-Id') ?? null
  const code = logicalStatus(res, body)
  if (!body || typeof body !== 'object') {
    return {
      detail: res.statusText || `Request failed (${code})`,
      requestId: headerId,
      code,
    }
  }
  const record = body as { request_id?: unknown; detail?: unknown; error?: unknown }
  const requestId =
    typeof record.request_id === 'string' && record.request_id ? record.request_id : headerId
  const detail = record.detail
  if (typeof detail === 'string') return { detail, requestId, code }
  if (Array.isArray(detail) && detail.length) {
    return {
      detail: detail
        .map((d: { loc?: (string | number)[]; msg?: string }) =>
          `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? 'invalid'}`,
        )
        .join('; '),
      requestId,
      code,
    }
  }
  if (detail) return { detail: JSON.stringify(detail), requestId, code }
  return {
    detail:
      (typeof record.error === 'string' && record.error) ||
      res.statusText ||
      `Request failed (${code})`,
    requestId,
    code,
  }
}

function withErrorId(detail: string, requestId: string | null): string {
  return requestId ? `${detail} (error id: ${requestId})` : detail
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  /** Skip the admin credential (used by the login and bootstrap calls). */
  anonymous?: boolean
}

async function parseJsonBody(
  res: Response,
  method: string,
  path: string,
): Promise<unknown> {
  try {
    const text = await res.text()
    return text ? JSON.parse(text) : undefined
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') throw error
    const detail = 'The backend returned an unreadable response.'
    const requestId = captureClientError(
      detail,
      'Response parsing failed; response contents were not recorded.',
      `${method} ${path}`,
    )
    throw new ApiError(res.status, withErrorId(detail, requestId), requestId)
  }
}

function throwIfFailed(
  res: Response,
  body: unknown,
  method: string,
  path: string,
  startedAt: number,
  anonymous?: boolean,
): void {
  const envelopeFailed = isEnvelopeFailure(body)
  const transportFailed = !res.ok
  if (!envelopeFailed && !transportFailed) return

  const { detail, requestId, code } = errorInfoFromBody(res, body)
  if (code === 401 && !anonymous) onUnauthorized()
  logApiError(method, path, code, detail, startedAt, requestId)
  throw new ApiError(code, withErrorId(detail, requestId), requestId ?? undefined)
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, anonymous } = options
  const startedAt = timerNow()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const payload = anonymous ? body : withSessionBody(body)
  if (!anonymous) Object.assign(headers, authHeaders())

  let res: Response
  try {
    res = await fetch(apiUrl(path), {
      method,
      headers,
      signal,
      body: payload === undefined ? undefined : JSON.stringify(payload),
    })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') throw err
    const detail = 'Cannot reach the backend. Is it running on port 9000?'
    logApiError(method, path, 0, detail, startedAt)
    const requestId = captureClientError(detail, (err as Error)?.message || '', `${method} ${path}`)
    throw new ApiError(0, withErrorId(detail, requestId), requestId)
  }

  if (res.status === 204) {
    logApiCall(method, path, 204, startedAt)
    return undefined as T
  }

  const parsed = await parseJsonBody(res, method, path)
  throwIfFailed(res, parsed, method, path, startedAt, anonymous)
  logApiCall(method, path, logicalStatus(res, parsed), startedAt)
  return parsed as T
}

/** Multipart upload: the browser sets the boundary Content-Type. */
export async function postForm<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  const startedAt = timerNow()
  const headers: Record<string, string> = { Accept: 'application/json', ...authHeaders() }
  const username = getUsername()
  const sessionId = getSessionId()
  if (username && !form.has('username')) form.append('username', username)
  if (sessionId && !form.has('session_id')) form.append('session_id', sessionId)

  let res: Response
  try {
    res = await fetch(apiUrl(path), { method: 'POST', headers, body: form, signal })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') throw err
    const detail = 'Cannot reach the backend. Is it running on port 9000?'
    logApiError('POST', path, 0, detail, startedAt)
    const requestId = captureClientError(detail, (err as Error)?.message || '', `POST ${path}`)
    throw new ApiError(0, withErrorId(detail, requestId), requestId)
  }
  const parsed = await parseJsonBody(res, 'POST', path)
  throwIfFailed(res, parsed, 'POST', path, startedAt)
  logApiCall('POST', path, logicalStatus(res, parsed), startedAt)
  return parsed as T
}

export const api = {
  get: <T,>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  postForm,
  post: <T,>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T,>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  patch: <T,>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  del: <T,>(path: string) => request<T>(path, { method: 'DELETE' }),
}
