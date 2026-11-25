/**
 * Persist the customer_care session while acting as a tenant admin so Exit
 * can restore the original operator without another login.
 */

const IMPERSONATOR_USER_ID_KEY = 'tenant-console.impersonator.user_id'
const IMPERSONATOR_USER_KEY = 'tenant-console.impersonator.username'
const IMPERSONATOR_SESSION_KEY = 'tenant-console.impersonator.session_id'
const IMPERSONATED_USER_KEY = 'tenant-console.impersonated.username'
const IMPERSONATED_TENANT_KEY = 'tenant-console.impersonated.tenant_id'

export function saveImpersonator(
  userId: string | number,
  sessionId: string,
  targetUsername: string,
  username?: string | null,
  tenantId?: string | null,
) {
  try {
    localStorage.setItem(IMPERSONATOR_USER_ID_KEY, String(userId).trim())
    localStorage.setItem(IMPERSONATOR_SESSION_KEY, sessionId.trim())
    localStorage.setItem(IMPERSONATED_USER_KEY, targetUsername.trim())
    if (username != null && String(username).trim()) {
      localStorage.setItem(IMPERSONATOR_USER_KEY, String(username).trim())
    }
    if (tenantId != null && String(tenantId).trim()) {
      localStorage.setItem(IMPERSONATED_TENANT_KEY, String(tenantId).trim())
    }
  } catch {
    /* private mode */
  }
}

export function clearImpersonator() {
  try {
    localStorage.removeItem(IMPERSONATOR_USER_ID_KEY)
    localStorage.removeItem(IMPERSONATOR_USER_KEY)
    localStorage.removeItem(IMPERSONATOR_SESSION_KEY)
    localStorage.removeItem(IMPERSONATED_USER_KEY)
    localStorage.removeItem(IMPERSONATED_TENANT_KEY)
  } catch {
    /* ignore */
  }
}

export function getImpersonator(): {
  userId: string
  sessionId: string
  username: string | null
  tenantId: string | null
} | null {
  try {
    const userId = localStorage.getItem(IMPERSONATOR_USER_ID_KEY)
    const sessionId = localStorage.getItem(IMPERSONATOR_SESSION_KEY)
    const username = localStorage.getItem(IMPERSONATOR_USER_KEY)
    const tenantId = localStorage.getItem(IMPERSONATED_TENANT_KEY)
    if (!userId || !sessionId) return null
    return { userId, sessionId, username, tenantId }
  } catch {
    return null
  }
}

export function getImpersonatedUsername(): string | null {
  try {
    return localStorage.getItem(IMPERSONATED_USER_KEY)
  } catch {
    return null
  }
}

export function getImpersonatedTenantId(): string | null {
  try {
    return localStorage.getItem(IMPERSONATED_TENANT_KEY)
  } catch {
    return null
  }
}

export function isImpersonating(): boolean {
  return getImpersonator() !== null
}
