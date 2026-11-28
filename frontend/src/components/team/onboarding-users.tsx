import { useMemo, useState } from 'react'
import { LogIn, Search, Users } from 'lucide-react'
import { adminsApi, isCustomerCareIdentity, type OnboardingUser } from '@/lib/admins'
import { useAuth } from '@/lib/auth'
import { useAsync, useAction } from '@/lib/hooks'
import { useTenants } from '@/lib/tenants'
import {
  ErrorBanner,
  GhostButton,
  Notice,
  Pill,
  PrimaryButton,
} from '@/components/remake/ui'
import { EmptyState, LoadingBlock } from '@/components/ui/feedback'
import { PageHeader } from '@/components/layout/page-header'
import { useToast } from '@/components/ui/toast'

/**
 * customer_care only: every tenant admin/sub-admin with a Login button that
 * opens that tenant as Customercare / superadmin (full access), using the
 * account's session under the hood for writes.
 */
export function OnboardingUsersPanel() {
  const { identity, loginAsUser } = useAuth()
  const { tenants } = useTenants()
  const toast = useToast()
  const action = useAction()
  const [search, setSearch] = useState('')
  const [opening, setOpening] = useState<string | null>(null)

  const allowed = isCustomerCareIdentity(identity)
  const users = useAsync(
    (signal) => (allowed ? adminsApi.onboardingUsers(signal) : Promise.resolve([] as OnboardingUser[])),
    [allowed, identity?.username],
  )

  const tenantName = useMemo(() => {
    const map = new Map<string, string>()
    for (const t of tenants) map.set(t.id, t.display_name || t.id)
    return map
  }, [tenants])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    const list = users.data ?? []
    if (!q) return list
    return list.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        (u.email || '').toLowerCase().includes(q) ||
        (u.tenant_id || '').toLowerCase().includes(q) ||
        (u.company_name || '').toLowerCase().includes(q) ||
        (u.website || '').toLowerCase().includes(q) ||
        (u.contact_number || '').toLowerCase().includes(q) ||
        (tenantName.get(u.tenant_id || '') || '').toLowerCase().includes(q),
    )
  }, [users.data, search, tenantName])

  if (!allowed) {
    return (
      <Notice tone="warn" title="Not permitted">
        Only the customer_care account can open onboarded users.
      </Notice>
    )
  }

  const openAs = async (user: OnboardingUser) => {
    setOpening(user.username)
    const ok = await action.run(() => loginAsUser(user.username))
    setOpening(null)
    if (ok !== null) toast.push(`Opened ${user.tenant_id || 'tenant'} as superadmin (via ${user.username})`)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        title="Onboarded users"
        description="Login into any tenant as Customercare superadmin, or open Privileges to grant menu access to tenant users."
        meta={<Pill tone="ok">{filtered.length} users</Pill>}
      />

      {(users.error || action.error) && (
        <div className="mb-4">
          <ErrorBanner message={users.error || action.error || ''} />
        </div>
      )}

      <div className="mb-4">
        <label className="flex max-w-md items-center gap-2 rounded-lg border border-line bg-inputbg px-2.5 py-1.5">
          <Search className="h-4 w-4 text-txfaint" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company, website, email, tenant…"
            className="w-full bg-transparent text-sm text-tx outline-none placeholder:text-txfaint"
          />
        </label>
      </div>

      {users.loading ? (
        <LoadingBlock label="Loading users…" />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Users className="h-7 w-7" />}
          title="No users found"
          description="Tenant admin accounts will appear here once they exist."
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-panel border border-line bg-card">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <thead className="sticky top-0 border-b border-line bg-paper text-xs uppercase tracking-wider text-txfaint">
              <tr>
                <th className="px-4 py-3 font-semibold">Company</th>
                <th className="px-4 py-3 font-semibold">Website</th>
                <th className="px-4 py-3 font-semibold">Tenant</th>
                <th className="px-4 py-3 font-semibold">Email</th>
                <th className="px-4 py-3 font-semibold">Contact</th>
                <th className="px-4 py-3 font-semibold">User / role</th>
                <th className="px-4 py-3 font-semibold">Onboarding</th>
                <th className="px-4 py-3 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-linesoft">
              {filtered.map((user) => (
                <tr key={`${user.tenant_id || ''}:${user.username}`} className="hover:bg-paper/60">
                  <td className="px-4 py-3">
                    <p className="font-medium text-tx">
                      {user.company_name ||
                        (user.tenant_id
                          ? tenantName.get(user.tenant_id) || user.tenant_id
                          : '—')}
                    </p>
                    {user.vertical ? (
                      <p className="text-[11px] text-txfaint">{user.vertical}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-txmuted">
                    {user.website ? (
                      <a
                        href={user.website}
                        target="_blank"
                        rel="noreferrer"
                        className="break-all text-xs text-attink hover:underline"
                      >
                        {user.website}
                      </a>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-mono text-xs text-tx">{user.tenant_id || 'Unassigned'}</p>
                  </td>
                  <td className="px-4 py-3 text-txmuted">{user.email || '—'}</td>
                  <td className="px-4 py-3 text-txmuted">
                    <p>{user.contact_number || '—'}</p>
                    {user.waba_phone_id &&
                    user.waba_phone_id !== user.contact_number ? (
                      <p className="text-[11px] text-txfaint">WA {user.waba_phone_id}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-tx">{user.username}</p>
                    <p className="text-xs text-txmuted">
                      {user.role === 'admin' ? 'admin' : 'sub admin'}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    {user.role === 'admin' ? (
                      user.onboarding_approved ? (
                        <Pill tone="ok">Approved</Pill>
                      ) : (
                        <Pill tone="warn">Pending</Pill>
                      )
                    ) : (
                      <span className="text-xs text-txfaint">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <PrimaryButton
                      className="px-3 py-1.5 text-xs"
                      disabled={Boolean(opening) || action.busy}
                      onClick={() => void openAs(user)}
                    >
                      <LogIn className="h-3.5 w-3.5" />
                      {opening === user.username ? 'Opening…' : 'Login'}
                    </PrimaryButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-3 text-xs text-txfaint">
        Login keeps you as Customercare superadmin inside that tenant. Use Exit in the banner to return.
      </p>
      {filtered.length > 0 && (
        <div className="mt-2">
          <GhostButton onClick={() => void users.reload()}>Refresh list</GhostButton>
        </div>
      )}
    </div>
  )
}
