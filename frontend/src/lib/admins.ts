import { api } from './api'
import type { AdminIdentity } from './types'

export interface AdminRecord {
  username: string
  email: string | null
  role: 'super_admin' | 'admin' | 'sub_admin'
  permissions: Record<string, boolean>
  created_at: string | null
  tenant_id?: string | null
}

export interface OnboardingUser {
  id: number | null
  username: string
  email: string | null
  role: 'admin' | 'sub_admin' | string
  tenant_id: string | null
  created_at: string | null
  onboarding_approved: boolean
}

export interface ImpersonateResult {
  status: string
  username: string
  session_id: string
  token: string
  role: string
  permissions: Record<string, boolean>
  tenant_id: string | null
  onboarding_approved: boolean
  session_minted?: boolean
  support_access?: boolean
}

/** Dedicated customer-care operator who may open tenant accounts. */
export function isCustomerCareIdentity(identity: {
  username?: string | null
  id?: number | null
  is_customer_care?: boolean
} | null): boolean {
  if (!identity) return false
  if (identity.is_customer_care) return true
  if ((identity.username || '').trim().toLowerCase() === 'customer_care') return true
  return Number(identity.id) === 3042
}

export const adminsApi = {
  list: () =>
    api.post<{ admins: AdminRecord[] }>('/api/auth/admins', {}).then((r) => r.admins),

  onboardingUsers: (signal?: AbortSignal) =>
    api
      .post<{ users: OnboardingUser[]; count: number }>('/api/auth/onboarding-users', {}, { signal })
      .then((r) => r.users),

  impersonate: (username: string) =>
    // Path param — not body `username` — because every panel POST injects the
    // caller's own username into the JSON body for session auth.
    api.post<ImpersonateResult>(
      `/api/auth/impersonate/${encodeURIComponent(username)}`,
      {},
    ),

  impersonateTenant: (tenantId: string) =>
    api.post<ImpersonateResult>(
      `/api/auth/impersonate-tenant/${encodeURIComponent(tenantId)}`,
      {},
    ),

  create: (body: {
    username: string
    password: string
    role?: string
    permissions?: Record<string, boolean> | null
    email?: string | null
    tenant_id?: string | null
  }) =>
    api.post<{ status: string; username: string; role: string; permissions: Record<string, boolean>; tenant_id?: string | null }>(
      '/api/auth/create',
      body,
    ),

  update: (
    username: string,
    // No `role` here on purpose: roles are fixed at creation and the API
    // refuses role changes — changing a role is delete + recreate.
    body: { permissions?: Record<string, boolean>; email?: string | null; tenant_id?: string | null },
  ) =>
    api.patch<{ status: string; username: string; role: string; permissions: Record<string, boolean>; tenant_id?: string | null }>(
      `/api/auth/admins/${encodeURIComponent(username)}`,
      body,
    ),

  remove: (username: string) => api.del<{ status: string }>(`/api/auth/admins/${encodeURIComponent(username)}`),

  resetPassword: (username: string, newPassword: string) =>
    api.post<{ status: string }>(`/api/auth/admins/${encodeURIComponent(username)}/reset-password`, {
      new_password: newPassword,
    }),

  me: () => api.get<AdminIdentity>('/api/auth/me'),
}
