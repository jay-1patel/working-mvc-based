import { api, apiUrl, ApiError, apiCallStart, authHeaders, logApiCall, logApiError } from './api'
import { type AuditEvent, type AuditFilters, type AuditPage } from './audit'
import { getImpersonator } from './impersonation'

/**
 * Activity log reads while support Login is active must use Customercare
 * credentials. The live session is the tenant admin, which hides
 * ``super_admin`` actor rows and would make the log look empty.
 */
async function auditPostAsViewer<T>(path: string, body: unknown = {}, signal?: AbortSignal): Promise<T> {
  const operator = getImpersonator()
  if (!operator) return api.post<T>(path, body, { signal })

  const startedAt = apiCallStart()
  const payload =
    body && typeof body === 'object'
      ? { ...(body as Record<string, unknown>), user_id: operator.userId, session_id: operator.sessionId }
      : { user_id: operator.userId, session_id: operator.sessionId }
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      user_id: operator.userId,
      session_id: operator.sessionId,
    },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail || res.statusText
    logApiError('POST', path, res.status, String(detail), startedAt)
    throw new ApiError(
      res.status,
      typeof detail === 'string' ? detail : `Request failed (${res.status})`,
    )
  }
  logApiCall('POST', path, res.status, startedAt)
  return (await res.json()) as T
}

// Extended audit types for new features
export interface AuditEventExtended extends Omit<AuditEvent, 'details'> {
  details: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  tenant_name?: string | null
  tenant_slug?: string | null
  tenant_label?: string
  actor_kind?: string | null
  actor_label?: string | null
  category?: string
  formatted_date?: string
  relative_time?: string
}

export interface AuditStatistics {
  total_events: number
  by_outcome: {
    success: number
    failure: number
  }
  by_action: Record<string, number>
  by_date: Record<string, number>
  by_category: Record<string, number>
  by_actor: Record<string, number>
}

// Extended filters
export interface AuditFiltersExtended extends AuditFilters {
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

// Export request
export interface ExportRequest {
  filters: AuditFiltersExtended
  format: 'csv' | 'json' | 'pdf'
  columns: string[]
}

// Realtime updates
export interface RealtimeUpdate {
  type: 'new' | 'updated' | 'deleted'
  event: AuditEventExtended
  timestamp: string
}

// Extended API functions
export const auditApiExtended = {
  // Original list function
  list: (filters: AuditFilters, signal?: AbortSignal) =>
    auditPostAsViewer<AuditPage>('/api/admin/audit-history', { ...filters }, signal),

  // New statistics endpoint
  getStatistics: (filters: AuditFilters, signal?: AbortSignal) =>
    auditPostAsViewer<AuditStatistics>('/api/admin/audit-statistics', { ...filters }, signal),

  // Export endpoint — returns a file blob (CSV / JSON / PDF), not JSON-parsed body.
  // Must not go through api.post(), which always JSON.parse()'s the response.
  exportEvents: async (request: ExportRequest, signal?: AbortSignal): Promise<Blob> => {
    const path = '/api/admin/audit-export'
    const body = {
      ...request.filters,
      format: request.format,
      columns: request.columns.join(','),
    }
    const startedAt = apiCallStart()
    let res: Response
    try {
      res = await fetch(apiUrl(path), {
        method: 'POST',
        headers: {
          Accept: '*/*',
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify(body),
        signal,
      })
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') throw err
      const detail = 'Cannot reach the backend. Is it running on port 9000?'
      logApiError('POST', path, 0, detail, startedAt)
      throw new ApiError(0, detail)
    }

    if (!res.ok) {
      let detail = `Export failed (${res.status})`
      try {
        const errBody = await res.json()
        if (typeof errBody?.detail === 'string') detail = errBody.detail
      } catch {
        /* body may be empty or non-JSON */
      }
      logApiError('POST', path, res.status, detail, startedAt)
      throw new ApiError(res.status, detail)
    }

    logApiCall('POST', path, res.status, startedAt)
    return res.blob()
  },

  // Get single event details
  getEvent: (eventId: number, signal?: AbortSignal) =>
    api.post<AuditEventExtended>(`/api/admin/audit-history/${eventId}`, {}, { signal }),

  // Real-time updates (WebSocket simulation via polling for now)
  subscribeUpdates: (_callback: (update: RealtimeUpdate) => void, signal?: AbortSignal) => {
    // This would be implemented with WebSocket in a real scenario
    // For now, we'll simulate with polling
    let intervalId: ReturnType<typeof setInterval>
    
    const poll = async () => {
      try {
        // In a real implementation, this would check for new events
        // For demo purposes, we'll just show the concept
      } catch (error) {
        console.error('Polling error:', error)
      }
    }
    
    if (!signal?.aborted) {
      intervalId = setInterval(poll, 30000) // Poll every 30 seconds
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }
}
