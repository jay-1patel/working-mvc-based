import { api, apiUrl, logApiCall, logApiError } from './api'
import { getImpersonator } from './impersonation'

/**
 * Tenant change requests: admins can view and edit the tenant registration
 * panel and tenant profiles, but every registration or publish they submit
 * lands in a queue only a super admin can approve. Mirrors the integration
 * request flow in `api-onboarding.ts`.
 */

export type TenantChangeType = 'create_tenant' | 'publish_profile'
export type TenantChangeStatus = 'pending' | 'approved' | 'rejected'

export interface TenantChangeRequest {
  id: number
  request_type: TenantChangeType
  tenant_id: string
  payload: {
    tenant?: {
      slug?: string
      vertical?: string
      display_name?: string
      waba_phone_id?: string
      status?: string
    }
    snapshot?: Record<string, unknown>
  }
  summary: string
  status: TenantChangeStatus
  requester_id: number | null
  requester_username: string
  reviewer_id: number | null
  reviewer_username: string | null
  decision_note: string
  decided_at: string | null
  applied: boolean | number
  applied_version: number | null
  created_at: string
  updated_at: string
  /** Tenant registry data at review time — the WhatsApp number is bound to
   * the tenants table, not the profile snapshot. */
  tenant_display_name?: string
  tenant_vertical?: string
  tenant_waba_phone_id?: string
}

export interface TenantChangeEvent {
  id: number
  request_id: number
  actor_id: number | null
  actor_username: string
  actor_role: string
  event_type: 'submitted' | 'decision'
  old_status: string | null
  new_status: string
  note: string
  created_at: string
}

export const tenantApprovalsApi = {
  mine: async (signal?: AbortSignal) =>
    (
      await api.post<{ requests: TenantChangeRequest[] }>(
        '/api/tenant-change-requests/mine',
        {},
        { signal },
      )
    ).requests,

  submitCreate: async (input: {
    tenant_id: string
    tenant: {
      slug?: string
      vertical?: string
      display_name?: string
      waba_phone_id?: string
      status?: string
    }
    snapshot?: object
    note?: string
  }) =>
    (
      await api.post<{ request: TenantChangeRequest }>('/api/tenant-change-requests', {
        request_type: 'create_tenant',
        ...input,
      })
    ).request,

  submitPublish: async (tenantId: string, note = '') =>
    (
      await api.post<{ request: TenantChangeRequest }>('/api/tenant-change-requests', {
        request_type: 'publish_profile',
        tenant_id: tenantId,
        note,
      })
    ).request,

  all: async (status?: TenantChangeStatus, signal?: AbortSignal) =>
    (
      await api.post<{ requests: TenantChangeRequest[] }>(
        '/api/admin/tenant-change-requests',
        status ? { status } : {},
        { signal },
      )
    ).requests,

  /**
   * Review queue as the super admin. While customer_care is logged into a
   * tenant via Onboarded users → Login, the live session is the tenant admin,
   * so this call uses the saved operator credentials instead.
   */
  allAsReviewer: async (status?: TenantChangeStatus, signal?: AbortSignal) => {
    const operator = getImpersonator()
    if (!operator) return tenantApprovalsApi.all(status, signal)

    const path = '/api/admin/tenant-change-requests'
    const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
    const payload: Record<string, unknown> = {
      user_id: operator.userId,
      session_id: operator.sessionId,
    }
    if (status) payload.status = status
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
      throw new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
    }
    logApiCall('POST', path, res.status, startedAt)
    const body = (await res.json()) as { requests: TenantChangeRequest[] }
    return body.requests
  },

  decide: async (id: number, decision: 'approved' | 'rejected', note: string) =>
    api.post<{ request: TenantChangeRequest; message: string }>(
      `/api/admin/tenant-change-requests/${id}/decision`,
      { decision, note },
    ),

  /** Approve/reject using customer_care credentials while inside a support Login. */
  decideAsReviewer: async (
    id: number,
    decision: 'approved' | 'rejected',
    note: string,
  ) => {
    const operator = getImpersonator()
    if (!operator) return tenantApprovalsApi.decide(id, decision, note)

    const path = `/api/admin/tenant-change-requests/${id}/decision`
    const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
    const body = {
      decision,
      note,
      user_id: operator.userId,
      session_id: operator.sessionId,
    }
    const res = await fetch(apiUrl(path), {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        user_id: operator.userId,
        session_id: operator.sessionId,
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const detail = (await res.json().catch(() => null))?.detail || res.statusText
      logApiError('POST', path, res.status, String(detail), startedAt)
      throw new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
    }
    logApiCall('POST', path, res.status, startedAt)
    return (await res.json()) as { request: TenantChangeRequest; message: string }
  },

  events: async (id: number, signal?: AbortSignal) =>
    (
      await api.post<{ events: TenantChangeEvent[] }>(
        `/api/admin/tenant-change-requests/${id}/events`,
        {},
        { signal },
      )
    ).events,
}
