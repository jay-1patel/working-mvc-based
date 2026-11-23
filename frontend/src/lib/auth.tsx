import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, getSessionId, getToken, getUsername, setCredentials, setToken, setUnauthorizedHandler } from './api'
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
  /** Restore the customer_care session saved before login-as. */
  exitImpersonation: () => Promise<void>
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
        const status = await api.get<{ has_admins: boolean }>('/api/auth/status')
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
        const me = await api.get<AdminIdentity>('/api/auth/me')
        if (cancelled) return
        setIdentity(me)
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
      permissions: Record<string, boolean>
    }>('/api/auth/login', { username, session_id: sessionId }, { anonymous: true })
    // Store username + session_id so every later API call sends them.
    setCredentials(res.username || username, res.session_id || sessionId)
    const me = await api.get<AdminIdentity>('/api/auth/me')
    setIdentity(me)
    setNeedsSetup(false)
    // Everyone lands on the graphical overview first.
    // Tenant admins open their tenant Today (charts + needs-you).
    // customer_care opens the onboarding-users roster; other super admins
    // open the platform dashboard.
    if (me.role !== 'super_admin' && me.tenant_id) {
      navigate(`/tenants/${encodeURIComponent(me.tenant_id)}/overview`)
    } else if (isCustomerCareIdentity(me)) {
      navigate('/onboarding-users')
    } else {
      navigate('/dashboard')
    }
  }, [])

  const setup = useCallback(async (username: string, password: string, email?: string) => {
    const res = await api.post<{ token: string }>('/api/auth/first-admin', {
      username,
      password,
      email: email || null,
    })
    setToken(res.token)
    const me = await api.get<AdminIdentity>('/api/auth/me')
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
      const me = await api.get<AdminIdentity>('/api/auth/me')
      setIdentity(me)
      return me
    } catch {
      /* leave the last known identity in place */
      return null
    }
  }, [])

  const loginAsUser = useCallback(async (username: string) => {
    const operatorUser = getUsername()
    const operatorSession = getSessionId()
    if (!operatorUser || !operatorSession) {
      throw new Error('Your customer_care session is missing — log in again')
    }
    const result = await adminsApi.impersonate(username)
    saveImpersonator(operatorUser, operatorSession, result.username)
    setCredentials(result.username, result.session_id)
    setImpersonating(true)
    setImpersonatedUsername(result.username)
    const me = await api.get<AdminIdentity>('/api/auth/me')
    setIdentity(me)
    if (me.tenant_id) {
      navigate(`/tenants/${encodeURIComponent(me.tenant_id)}/overview`)
    } else {
      navigate('/dashboard')
    }
  }, [])

  const exitImpersonation = useCallback(async () => {
    const operator = getImpersonator()
    if (!operator) {
      clearImpersonator()
      setImpersonating(false)
      setImpersonatedUsername(null)
      return
    }
    setCredentials(operator.username, operator.sessionId)
    clearImpersonator()
    setImpersonating(false)
    setImpersonatedUsername(null)
    const me = await api.get<AdminIdentity>('/api/auth/me')
    setIdentity(me)
    navigate('/onboarding-users')
  }, [])

  const can = useCallback(
    (permission: string) => {
      if (!identity) return false
      // Only a super admin bypasses the switch list; admins and sub admins
      // are granted exactly what /api/auth/me reports (the stored set).
      if (identity.role === 'super_admin') return true
      return Boolean(identity.permissions?.[permission])
    },
    [identity],
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
