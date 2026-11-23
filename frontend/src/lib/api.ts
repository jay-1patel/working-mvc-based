/**
 * Single fetch wrapper for the whole app.
 *
 * After login, every API call passes the live admin session_id as:
 *   - Authorization: Basic base64(username:session_id)
 *   - X-Username / X-Session-Id headers
 *   - session_id field on JSON request bodies
 *
 * Every non-2xx response is normalised into an `ApiError` carrying the
 * server's `detail`, so screens can surface backend validation text.
 */

import { captureClientError } from './client-errors'

const TOKEN_KEY = 'tenant-console.token'
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

/** Persist username + session_id and the Basic token derived from them. */
export function setCredentials(username: string, sessionId: string) {
  const user = username.trim()
  const session = sessionId.trim()
  const token = btoa(`${user}:${session}`)
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USERNAME_KEY, user)
    localStorage.setItem(SESSION_KEY, session)
  } catch {
    /* private mode — the session simply does not persist */
  }
}

export function setToken(token: string | null) {
  try {
    if (!token) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USERNAME_KEY)
      localStorage.removeItem(SESSION_KEY)
      return
    }
    localStorage.setItem(TOKEN_KEY, token)
    try {
      const decoded = atob(token)
      const idx = decoded.indexOf(':')
      if (idx > 0) {
        localStorage.setItem(USERNAME_KEY, decoded.slice(0, idx))
        localStorage.setItem(SESSION_KEY, decoded.slice(idx + 1))
      }
    } catch {
      /* keep whatever username/session keys already exist */
    }
  } catch {
    /* private mode — the session simply does not persist */
  }
}

/** Auth headers — lowercase username + session_id (no Authorization). */
export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const username = getUsername()
  const sessionId = getSessionId()
  if (username) headers.username = username
  if (sessionId) headers.session_id = sessionId
  return headers
}

/** Attach lowercase username + session_id on every JSON body. */
function withSessionBody(body: unknown): unknown {
  const username = getUsername()
  const sessionId = getSessionId()
  if ((!username && !sessionId) || body === undefined || body === null) return body
  if (typeof body === 'object' && !Array.isArray(body)) {
    return {
      ...(body as Record<string, unknown>),
      ...(username ? { username } : {}),
      ...(sessionId ? { session_id: sessionId } : {}),
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

/** Detail text plus the backend request_id (body field first, then the
 * X-Request-Id header the Phase-1 middleware stamps on every response). */
async function readErrorInfo(
  res: Response,
): Promise<{ detail: string; requestId: string | null }> {
  const headerId = res.headers?.get?.('X-Request-Id') ?? null
  try {
    const body = await res.json()
    const requestId =
      typeof body?.request_id === 'string' && body.request_id ? body.request_id : headerId
    const detail = body?.detail
    if (typeof detail === 'string') return { detail, requestId }
    if (Array.isArray(detail) && detail.length) {
      // pydantic validation errors
      return {
        detail: detail
          .map((d: { loc?: (string | number)[]; msg?: string }) =>
            `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? 'invalid'}`,
          )
          .join('; '),
        requestId,
      }
    }
    if (detail) return { detail: JSON.stringify(detail), requestId }
    return { detail: body?.error || res.statusText || `Request failed (${res.status})`, requestId }
  } catch {
    return { detail: res.statusText || `Request failed (${res.status})`, requestId: headerId }
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

async function parseResponse<T>(res: Response, method: string, path: string): Promise<T> {
  try {
    const text = await res.text()
    return (text ? JSON.parse(text) : undefined) as T
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') throw error
    const detail = 'The backend returned an unreadable response.'
    const requestId = captureClientError(detail, 'Response parsing failed; response contents were not recorded.', `${method} ${path}`)
    throw new ApiError(res.status, withErrorId(detail, requestId), requestId)
  }
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

  if (res.status === 401) {
    if (!anonymous) onUnauthorized()
    const { detail, requestId } = await readErrorInfo(res)
    logApiError(method, path, 401, detail, startedAt, requestId)
    throw new ApiError(401, withErrorId(detail, requestId), requestId ?? undefined)
  }
  if (!res.ok) {
    const { detail, requestId } = await readErrorInfo(res)
    logApiError(method, path, res.status, detail, startedAt, requestId)
    throw new ApiError(res.status, withErrorId(detail, requestId), requestId ?? undefined)
  }
  logApiCall(method, path, res.status, startedAt)
  if (res.status === 204) return undefined as T
  return parseResponse<T>(res, method, path)
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
  if (res.status === 401) {
    onUnauthorized()
    const { detail, requestId } = await readErrorInfo(res)
    logApiError('POST', path, 401, detail, startedAt, requestId)
    throw new ApiError(401, withErrorId(detail, requestId), requestId ?? undefined)
  }
  if (!res.ok) {
    const { detail, requestId } = await readErrorInfo(res)
    logApiError('POST', path, res.status, detail, startedAt, requestId)
    throw new ApiError(res.status, withErrorId(detail, requestId), requestId ?? undefined)
  }
  logApiCall('POST', path, res.status, startedAt)
  return parseResponse<T>(res, 'POST', path)
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
