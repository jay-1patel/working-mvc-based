import { getToken } from './api'

interface ClientError {
  message: string
  detail: string
  page: string
  api: string
  request_id: string
  occurred_at: string
}

// Bounded in-memory queue: backend outages can be reported after reconnection.
// Diagnostic text only; never include headers, form data, or request bodies.
const pending: { payload: ClientError; token: string }[] = []
let sending = false

export function captureClientError(message: string, detail = '', api = 'browser'): string {
  const suffix = typeof crypto.randomUUID === 'function' ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('')
  const id = `client_${suffix}`
  const token = getToken()
  if (!token) return id
  pending.push({ token, payload: { message: message.slice(0, 500), detail: detail.slice(-4000),
    page: (window.location.pathname + window.location.hash).split('?')[0].slice(0, 300),
    api: api.split('?')[0].slice(0, 200), request_id: id, occurred_at: new Date().toISOString() } })
  if (pending.length > 50) pending.splice(1, 1)
  void flushClientErrors()
  return id
}

export async function flushClientErrors(): Promise<void> {
  if (sending || !pending.length) return
  sending = true
  try {
    while (pending.length) {
      const event = pending[0]
      // Never attribute a queued event to someone who signed in afterwards.
      if (!getToken() || getToken() !== event.token) { pending.shift(); continue }
      let username = ''
      let sessionId = ''
      try {
        const decoded = atob(event.token)
        const idx = decoded.indexOf(':')
        if (idx > 0) {
          username = decoded.slice(0, idx)
          sessionId = decoded.slice(idx + 1)
        }
      } catch {
        /* ignore decode errors; Basic header still sent */
      }
      const response = await fetch('/api/client-errors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(username ? { username } : {}),
          ...(sessionId ? { session_id: sessionId } : {}),
        },
        body: JSON.stringify({
          ...event.payload,
          ...(username ? { username } : {}),
          ...(sessionId ? { session_id: sessionId } : {}),
        }),
      })
      if (response.status === 401) { pending.shift(); continue }
      // Drop rejected events, but retry transient backend failures later.
      if (!response.ok && response.status >= 500) break
      pending.shift()
    }
  } catch { /* Offline: keep the bounded queue until the next retry. */ }
  finally { sending = false }
}

export function installClientErrorReporting(): () => void {
  const onError = (event: ErrorEvent) => {
    if (event.message) captureClientError(event.message, event.error?.stack || `${event.filename}:${event.lineno}:${event.colno}`)
  }
  const onRejection = (event: PromiseRejectionEvent) => {
    captureClientError(event.reason instanceof Error ? event.reason.message : 'Unhandled promise rejection',
      event.reason instanceof Error ? event.reason.stack : '')
  }
  const onOnline = () => { void flushClientErrors() }
  window.addEventListener('error', onError)
  window.addEventListener('unhandledrejection', onRejection)
  window.addEventListener('online', onOnline)
  const timer = window.setInterval(onOnline, 30_000)
  return () => {
    window.removeEventListener('error', onError)
    window.removeEventListener('unhandledrejection', onRejection)
    window.removeEventListener('online', onOnline)
    window.clearInterval(timer)
  }
}
