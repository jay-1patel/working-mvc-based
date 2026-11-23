/**
 * Persist the customer_care session while acting as a tenant admin so Exit
 * can restore the original operator without another login.
 */

const IMPERSONATOR_USER_KEY = 'tenant-console.impersonator.username'
const IMPERSONATOR_SESSION_KEY = 'tenant-console.impersonator.session_id'
const IMPERSONATED_USER_KEY = 'tenant-console.impersonated.username'

export function saveImpersonator(username: string, sessionId: string, targetUsername: string) {
  try {
    localStorage.setItem(IMPERSONATOR_USER_KEY, username.trim())
    localStorage.setItem(IMPERSONATOR_SESSION_KEY, sessionId.trim())
    localStorage.setItem(IMPERSONATED_USER_KEY, targetUsername.trim())
  } catch {
    /* private mode */
  }
}

export function clearImpersonator() {
  try {
    localStorage.removeItem(IMPERSONATOR_USER_KEY)
    localStorage.removeItem(IMPERSONATOR_SESSION_KEY)
    localStorage.removeItem(IMPERSONATED_USER_KEY)
  } catch {
    /* ignore */
  }
}

export function getImpersonator(): { username: string; sessionId: string } | null {
  try {
    const username = localStorage.getItem(IMPERSONATOR_USER_KEY)
    const sessionId = localStorage.getItem(IMPERSONATOR_SESSION_KEY)
    if (!username || !sessionId) return null
    return { username, sessionId }
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

export function isImpersonating(): boolean {
  return getImpersonator() !== null
}
