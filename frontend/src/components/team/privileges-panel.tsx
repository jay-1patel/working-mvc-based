import { useMemo, useState } from 'react'
import { KeyRound } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { useAsync, useAction } from '@/lib/hooks'
import {
  MENU_PRIVILEGE_KEYS,
  emptyMenuPrivileges,
  menuPrivilegesApi,
  privilegesFromItems,
  type MenuPrivilegeMeta,
  type PrivilegeDropdownUser,
} from '@/lib/menu-privileges'
import {
  ErrorBanner,
  Notice,
  Pill,
  PrimaryButton,
  GhostButton,
} from '@/components/remake/ui'
import { LoadingBlock } from '@/components/ui/feedback'
import { PageHeader } from '@/components/layout/page-header'
import { useToast } from '@/components/ui/toast'
import { cn } from '@/lib/cn'

/**
 * Superadmin Privileges page:
 * 1) dropdown of users (id + username)
 * 2) load that user's menus active/inactive
 * 3) save
 */
export function PrivilegesPanel() {
  const { identity } = useAuth()
  const toast = useToast()
  const action = useAction()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedUsername, setSelectedUsername] = useState<string>('')
  const [draft, setDraft] = useState<Record<string, boolean>>(emptyMenuPrivileges())
  const [items, setItems] = useState<MenuPrivilegeMeta[]>([])
  const [editable, setEditable] = useState(true)
  const [loadingUser, setLoadingUser] = useState(false)

  const allowed = identity?.role === 'super_admin'
  const usersReq = useAsync(
    (signal) =>
      allowed
        ? menuPrivilegesApi.users(signal)
        : Promise.resolve({ ok: true, action: 'users', users: [] as PrivilegeDropdownUser[], count: 0 }),
    [allowed, identity?.username, identity?.id],
  )

  const users = usersReq.data?.users ?? []

  const selectedUser = useMemo(
    () => users.find((u) => u.id === selectedId) ?? null,
    [users, selectedId],
  )

  const onSelectUser = async (value: string) => {
    if (!value) {
      setSelectedId(null)
      setSelectedUsername('')
      setDraft(emptyMenuPrivileges())
      setItems([])
      setEditable(true)
      return
    }
    const uid = Number(value)
    const user = users.find((u) => u.id === uid)
    if (!user) return
    setSelectedId(uid)
    setSelectedUsername(user.username)
    setLoadingUser(true)
    try {
      const detail = await menuPrivilegesApi.get({ id: uid })
      setItems(detail.items || [])
      setDraft({
        ...emptyMenuPrivileges(),
        ...(detail.privileges || privilegesFromItems(detail.items)),
      })
      setEditable(detail.editable !== false)
    } catch (err) {
      setDraft(emptyMenuPrivileges())
      setItems([])
      toast.push((err as Error)?.message || 'Could not load privileges')
    } finally {
      setLoadingUser(false)
    }
  }

  const toggle = (key: string) => {
    if (!editable) return
    setDraft((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const setAll = (enabled: boolean) => {
    if (!editable) return
    setDraft(Object.fromEntries(MENU_PRIVILEGE_KEYS.map((k) => [k, enabled])))
  }

  const save = async () => {
    if (selectedId == null) return
    const result = await action.run(() =>
      menuPrivilegesApi.save({
        id: selectedId,
        privileges: draft,
      }),
    )
    if (result) {
      toast.push(`Privileges saved for ${selectedUsername}`)
      setItems(result.items || [])
      setDraft({
        ...emptyMenuPrivileges(),
        ...(result.privileges || privilegesFromItems(result.items)),
      })
    }
  }

  if (!allowed) {
    return (
      <Notice tone="warn" title="Not permitted">
        Only a superadmin can manage menu privileges.
      </Notice>
    )
  }

  const rows =
    items.length > 0
      ? items
      : MENU_PRIVILEGE_KEYS.map((key) => ({
          key,
          label: key,
          description: '',
          active: Boolean(draft[key]),
        }))

  const grantedCount = Object.values(draft).filter(Boolean).length

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        title="Privileges"
        description="Select an admin from the dropdown, set menus active/inactive, then save."
        meta={<Pill tone="ok">{users.length} users</Pill>}
      />

      <div className="mb-4">
        <Notice tone="success" title="Superadmin">
          Superadmin always has all menus. This page only assigns privileges to admin / sub-admin.
        </Notice>
      </div>

      {(usersReq.error || action.error) && (
        <div className="mb-4">
          <ErrorBanner message={usersReq.error || action.error || ''} />
        </div>
      )}

      {usersReq.loading ? (
        <LoadingBlock label="Loading users…" />
      ) : (
        <div className="mb-4 max-w-lg">
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-txfaint">
            Select user
          </label>
          <select
            className="w-full rounded-lg border border-line bg-inputbg px-3 py-2.5 text-sm text-tx outline-none"
            value={selectedId ?? ''}
            onChange={(e) => void onSelectUser(e.target.value)}
          >
            <option value="">Select user…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username} (id {u.id}) · {u.role}
              </option>
            ))}
          </select>
        </div>
      )}

      {!selectedUser ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-sm text-txmuted">
          <KeyRound className="h-7 w-7 text-txfaint" />
          <p>Select a user to view and edit menu privileges.</p>
        </div>
      ) : loadingUser ? (
        <LoadingBlock label="Loading privileges…" />
      ) : (
        <div className="max-w-xl rounded-panel border border-line bg-card p-4">
          <div className="mb-3 border-b border-line pb-3">
            <p className="text-sm font-semibold text-tx">{selectedUser.username}</p>
            <p className="text-xs text-txmuted">
              id {selectedUser.id} · {selectedUser.role}
            </p>
            <p className="mt-1 text-xs text-txfaint">
              {editable
                ? `${grantedCount} of ${MENU_PRIVILEGE_KEYS.length} menus active`
                : 'All menus always active'}
            </p>
          </div>

          {!editable ? (
            <div className="mb-3">
              <Notice tone="success" title="Locked">
                This account always has all menus active.
              </Notice>
            </div>
          ) : (
            <div className="mb-3 flex gap-2">
              <GhostButton type="button" onClick={() => setAll(true)}>
                All active
              </GhostButton>
              <GhostButton type="button" onClick={() => setAll(false)}>
                All inactive
              </GhostButton>
            </div>
          )}

          <div className="space-y-2">
            {rows.map((item) => {
              const key = String(item.key || item.permission || '')
              const on = Boolean(draft[key])
              return (
                <label
                  key={key}
                  className={cn(
                    'flex gap-3 rounded-lg border px-3 py-2.5',
                    editable ? 'cursor-pointer' : 'cursor-default',
                    on ? 'border-acc/40 bg-accsoft/30' : 'border-line bg-paper',
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={on}
                    disabled={!editable}
                    onChange={() => toggle(key)}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-tx">
                      {item.label || item.menu_name || key}
                    </span>
                    <span className="mt-0.5 block font-mono text-xs text-txfaint">
                      id {item.id ?? '—'} · {key} · {on ? 'active' : 'inactive'}
                    </span>
                    {item.description ? (
                      <span className="mt-0.5 block text-xs leading-snug text-txmuted">
                        {item.description}
                      </span>
                    ) : null}
                  </span>
                </label>
              )
            })}
          </div>

          {editable ? (
            <div className="mt-4 border-t border-line pt-3">
              <PrimaryButton
                type="button"
                disabled={action.busy}
                onClick={() => void save()}
                className="w-full"
              >
                {action.busy ? 'Saving…' : 'Save privileges'}
              </PrimaryButton>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
