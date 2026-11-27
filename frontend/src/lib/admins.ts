import { api } from './api'
import type { AdminIdentity } from './types'

export interface AdminRecord {
  id?: number | null
  user_id?: number | null
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
  /** Company / tenant details for the roster under that tenant. */
  company_name?: string | null
  website?: string | null
  contact_number?: string | null
  mobile_number?: string | null
  waba_phone_id?: string | null
  vertical?: string | null
}

export interface OnboardingTenant {
  id: string
  slug: string
  display_name: string
  vertical: string
  waba_phone_id?: string | null
}

export interface ImpersonateResult {
  status: string
  id?: number | null
  user_id?: number | null
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

  /** Signup-assigned tenant for Set up chatbot (company admin only). */
  onboardingTenants: (signal?: AbortSignal) =>
    api
      .post<{ tenants: OnboardingTenant[]; count: number }>(
        '/api/auth/onboarding-tenants',
        {},
        { signal },
      )
      .then((r) => r.tenants),

  impersonate: (username: string) =>
    // Path param — not body `username` — so the target name is not confused
    // with session auth (username + session_id headers).
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
    api.post<{ status: string; username: string; role: string; permissions: Record<string, boolean>; tenant_id?: string | null }>(
      `/api/auth/admins/${encodeURIComponent(username)}/update`,
      body,
    ),

  remove: (username: string) =>
    api.post<{ status: string }>(`/api/auth/admins/${encodeURIComponent(username)}/delete`, {}),

  resetPassword: (username: string, newPassword: string) =>
    api.post<{ status: string }>(`/api/auth/admins/${encodeURIComponent(username)}/reset-password`, {
      new_password: newPassword,
    }),

  me: () => api.post<AdminIdentity>('/api/auth/me', {}),

  /** Set up chatbot: configure signup tenant (WhatsApp + brand).
   * tenant_id comes from the session admin — do not send it in the body.
   * Upload kit/brochure files via ``firstLoginUpload`` after this succeeds. */
  firstLoginComplete: (body: {
    waba_phone_id?: string
    mobile_number?: string
    snapshot: Record<string, unknown>
  }) =>
    api.post<{
      ok: boolean
      tenant_id: string
      version: number
      vertical: string
      username: string
      onboarding_approved: boolean
    }>('/api/auth/first-login/complete', body),

  /** Upload kit/brochure data after first-login/complete.
   * tenant_id comes from the session admin — do not send it in the body. */
  firstLoginUpload: (body: {
    files?: Array<{ filename: string; content: string }>
    lane?: 'kit' | 'any'
    upload_draft?: Record<string, unknown>
  }) =>
    api.post<{
      ok: boolean
      tenant_id: string
      username: string
      upload: { status: string; summary?: unknown; detail?: string }
    }>('/api/auth/first-login/upload', body),
}
