import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  api,
  apiUrl,
  getSessionId,
  getToken,
  getUserId,
  getUsername,
  setActiveTenantId,
  setCredentials,
  setToken,
  setUnauthorizedHandler,
} from './api'
import { navigate } from './router'
import type { AdminIdentity } from './types'
import { isMockMode, mockIdentity } from './mock'
import {
  clearImpersonator,
  getImpersonatedUsername,
  getImpersonator,
  isImpersonating as readImpersonating,
  saveImpersonator,
} from './impersonation'
import { adminsApi, isCustomerCareIdentity } from './admins'

/** /api/auth/me with explicit credentials (used to keep Customercare identity while supporting). */
async function fetchIdentityAs(userId: string | number, sessionId: string): Promise<AdminIdentity> {
  const res = await fetch(apiUrl('/api/auth/me'), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      user_id: String(userId),
      session_id: sessionId,
    },
    body: JSON.stringify({ user_id: userId, session_id: sessionId }),
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail || res.statusText
    throw new Error(typeof detail === 'string' ? detail : `Could not load identity (${res.status})`)
  }
  return (await res.json()) as AdminIdentity
}

interface AuthState {
  loading: boolean
  /** The server has no admin accounts yet — the UI offers first-run setup. */
  needsSetup: boolean
  identity: AdminIdentity | null
  /** True while customer_care is acting as a tenant admin. */
  impersonating: boolean
  impersonatedUsername: string | null
  login: (username: string, sessionId: string) => Promise<void>
  setup: (username: string, password: string, email?: string) => Promise<void>
  logout: () => void
  can: (permission: string) => boolean
  /** Re-read the current admin (e.g. to notice an onboarding approval). */
  refreshIdentity: () => Promise<AdminIdentity | null>
  /** customer_care: open a tenant admin's live session. */
  loginAsUser: (username: string) => Promise<void>
  /** customer_care: open a tenant as its primary admin (full support UI). */
  loginAsTenant: (tenantId: string) => Promise<void>
  /** Restore the customer_care session saved before login-as. */
  exitImpersonation: (redirectTo?: string) => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [identity, setIdentity] = useState<AdminIdentity | null>(null)
  const [impersonating, setImpersonating] = useState(() => readImpersonating())
  const [impersonatedUsername, setImpersonatedUsername] = useState<string | null>(() =>
    getImpersonatedUsername(),
  )

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null)
      setIdentity(null)
      clearImpersonator()
      setImpersonating(false)
      setImpersonatedUsername(null)
    })
  }, [])

  useEffect(() => {
    if (isMockMode()) {
      setIdentity(mockIdentity)
      setNeedsSetup(false)
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const status = await api.post<{ has_admins: boolean }>('/api/auth/status', {})
        if (cancelled) return
        if (!status.has_admins) {
          setNeedsSetup(true)
          setLoading(false)
          return
        }
        if (!getToken()) {
          setLoading(false)
          return
        }
        // Support Login keeps the tenant-admin session for API writes, but the
        // UI identity must stay Customercare / superadmin.
        const operator = getImpersonator()
        if (operator) {
          setImpersonating(true)
          setImpersonatedUsername(getImpersonatedUsername())
          const me = await fetchIdentityAs(operator.userId, operator.sessionId)
          if (cancelled) return
          setIdentity(me)
        } else {
          const me = await api.post<AdminIdentity>('/api/auth/me', {})
          if (cancelled) return
          // Backfill user_id if this browser still has a legacy username token.
          if (me?.id != null && !getUserId()) {
            setCredentials(me.id, getSessionId() || '', me.username)
          }
          setIdentity(me)
        }
      } catch {
        if (!cancelled) setIdentity(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, sessionId: string) => {
    const res = await api.post<{
      token: string
      session_id?: string
      username?: string
      id?: number
      user_id?: number
      permissions: Record<string, boolean>
    }>('/api/auth/login', { username, session_id: sessionId }, { anonymous: true })
    const resolvedId = res.user_id ?? res.id
    if (resolvedId == null || String(resolvedId).trim() === '') {
      throw new Error('Login response missing user_id')
    }
    // Store user_id + session_id so every later API call sends them.
    setCredentials(resolvedId, res.session_id || sessionId, res.username || username)
    const me = await api.post<AdminIdentity>('/api/auth/me', {})
    setIdentity(me)
    setNeedsSetup(false)
    // Everyone lands on the graphical overview first.
    // Tenant admins open their tenant Today (charts + needs-you).
    // customer_care opens the onboarding-users roster; other super admins
    // open the platform dashboard.
    if (me.role === 'admin' && !me.tenant_id) {
      navigate('/register')
    } else if (me.role !== 'super_admin' && me.tenant_id) {
      navigate(`/tenants/${encodeURIComponent(me.tenant_id)}/overview`)
    } else if (isCustomerCareIdentity(me)) {
      navigate('/onboarding-users')
    } else {
      navigate('/dashboard')
    }
  }, [])

  const setup = useCallback(async (username: string, password: string, email?: string) => {
    const res = await api.post<{ token: string; id?: number; user_id?: number; session_id?: string }>(
      '/api/auth/first-admin',
      {
        username,
        password,
        email: email || null,
      },
    )
    const userId = res.user_id ?? res.id
    if (userId != null && (res.session_id || getSessionId())) {
      setCredentials(userId, res.session_id || getSessionId() || '', username)
    } else {
      setToken(res.token)
    }
    const me = await api.post<AdminIdentity>('/api/auth/me', {})
    if (me?.id != null) {
      setCredentials(me.id, getSessionId() || res.session_id || '', me.username)
    }
    setIdentity(me)
    setNeedsSetup(false)
    navigate('/dashboard')
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setIdentity(null)
    clearImpersonator()
    setImpersonating(false)
    setImpersonatedUsername(null)
  }, [])

  const refreshIdentity = useCallback(async () => {
    try {
      const operator = getImpersonator()
      const me = operator
        ? await fetchIdentityAs(operator.userId, operator.sessionId)
        : await api.post<AdminIdentity>('/api/auth/me', {})
      if (me?.id != null && !getUserId() && !operator) {
        setCredentials(me.id, getSessionId() || '', me.username)
      }
      setIdentity(me)
      return me
    } catch {
      /* leave the last known identity in place */
      return null
    }
  }, [])

  const applySupportSession = useCallback(async (result: Awaited<ReturnType<typeof adminsApi.impersonate>>) => {
    const operatorUserId = getUserId()
    const operatorSession = getSessionId()
    if (!operatorUserId || !operatorSession) {
      throw new Error('Your customer_care session is missing — log in again')
    }
    if (!result.tenant_id) {
      throw new Error('That account is not assigned to a tenant')
    }
    const sessionId = String(result.session_id || '').trim()
    if (!sessionId) {
      throw new Error(
        `Admin "${result.username}" has no session_id in the database. Regenerate their session, then try Login again.`,
      )
    }
    const targetUserId = result.user_id ?? result.id
    if (targetUserId == null) {
      throw new Error(`Admin "${result.username}" has no user_id in the login payload`)
    }
    // Keep Customercare / superadmin as the visible identity. The live API
    // session switches to the tenant account so writes are allowed.
    const operatorIdentity =
      identity && isCustomerCareIdentity(identity)
        ? identity
        : await fetchIdentityAs(operatorUserId, operatorSession)
    saveImpersonator(
      operatorUserId,
      operatorSession,
      result.username,
      getUsername(),
      result.tenant_id,
    )
    setCredentials(targetUserId, sessionId, result.username)
    setActiveTenantId(result.tenant_id)
    setImpersonating(true)
    setImpersonatedUsername(result.username)
    setIdentity({
      ...operatorIdentity,
      role: 'super_admin',
      onboarding_approved: true,
      is_customer_care: true,
    })
    navigate(`/tenants/${encodeURIComponent(result.tenant_id)}/overview`)
  }, [identity])

  const loginAsUser = useCallback(
    async (username: string) => {
      const result = await adminsApi.impersonate(username)
      await applySupportSession(result)
    },
    [applySupportSession],
  )

  const loginAsTenant = useCallback(
    async (tenantId: string) => {
      const result = await adminsApi.impersonateTenant(tenantId)
      await applySupportSession(result)
    },
    [applySupportSession],
  )

  const exitImpersonation = useCallback(async (redirectTo = '/onboarding-users') => {
    const operator = getImpersonator()
    if (!operator) {
      clearImpersonator()
      setImpersonating(false)
      setImpersonatedUsername(null)
      return
    }
    setCredentials(operator.userId, operator.sessionId, operator.username)
    clearImpersonator()
    setImpersonating(false)
    setImpersonatedUsername(null)
    const me = await api.post<AdminIdentity>('/api/auth/me', {})
    setIdentity(me)
    navigate(redirectTo)
  }, [])

  const can = useCallback(
    (permission: string) => {
      if (!identity) return false
      // customer_care support session: full console access inside the tenant.
      if (impersonating) return true
      // Only a super admin bypasses the switch list; admins and sub admins
      // are granted exactly what /api/auth/me reports (the stored set).
      if (identity.role === 'super_admin') return true
      return Boolean(identity.permissions?.[permission])
    },
    [identity, impersonating],
  )

  const value = useMemo(
    () => ({
      loading,
      needsSetup,
      identity,
      impersonating,
      impersonatedUsername,
      login,
      setup,
      logout,
      can,
      refreshIdentity,
      loginAsUser,
      loginAsTenant,
      exitImpersonation,
    }),
    [
      loading,
      needsSetup,
      identity,
      impersonating,
      impersonatedUsername,
      login,
      setup,
      logout,
      can,
      refreshIdentity,
      loginAsUser,
      loginAsTenant,
      exitImpersonation,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
