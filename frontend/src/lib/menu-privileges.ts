import { api } from './api'

/** Menu permission keys (menu_privilege.permission). */
export const MENU_PRIVILEGE_KEYS = [
  'graphic',
  'chats',
  'profile',
  'customer',
  'website_crawler',
  'setup_chatbot',
  'menu',
] as const

export type MenuPrivilegeKey = (typeof MENU_PRIVILEGE_KEYS)[number]

export interface MenuPrivilegeMeta {
  id?: number | null
  key: MenuPrivilegeKey | string
  menu_name?: string
  permission?: string
  label: string
  description: string
  flag?: number
  active?: boolean
}

export interface PrivilegeDropdownUser {
  id: number
  user_id: number
  username: string
  role: string
  tenant_id?: string | null
  email?: string | null
}

export interface PrivilegeGrantRow {
  id?: string
  user_id: number
  privileges_id: number
  privileges_name: string
  flag?: number
  createdOn?: string | null
  updatedOn?: string | null
}

export interface PrivilegeRow {
  user_id: number
  items?: MenuPrivilegeMeta[]
}

/** Nav view ids gated by each menu privilege. */
export const MENU_PRIVILEGE_TO_NAV_IDS: Record<MenuPrivilegeKey, string[]> = {
  graphic: ['overview'],
  chats: ['inbox'],
  profile: ['profile'],
  customer: ['customers'],
  website_crawler: ['website-crawler', 'uploads', 'website-knowledge'],
  setup_chatbot: ['profile-menu', 'settings'],
  menu: ['menu'],
}

/** Reverse map: nav id → privilege key that must be granted. */
export const NAV_ID_TO_MENU_PRIVILEGE: Record<string, MenuPrivilegeKey> = (() => {
  const out: Record<string, MenuPrivilegeKey> = {}
  for (const key of MENU_PRIVILEGE_KEYS) {
    for (const navId of MENU_PRIVILEGE_TO_NAV_IDS[key]) {
      out[navId] = key
    }
  }
  return out
})()

export function emptyMenuPrivileges(): Record<string, boolean> {
  return Object.fromEntries(MENU_PRIVILEGE_KEYS.map((k) => [k, false]))
}

export function allMenuPrivileges(enabled = true): Record<string, boolean> {
  return Object.fromEntries(MENU_PRIVILEGE_KEYS.map((k) => [k, enabled]))
}

export function menuIdsFromPrivileges(privileges: Record<string, boolean>): string[] {
  return MENU_PRIVILEGE_KEYS.filter((k) => Boolean(privileges[k]))
}

export function privilegesFromMenuIds(menuIds: string[] | null | undefined): Record<string, boolean> {
  const set = new Set(menuIds || [])
  return Object.fromEntries(MENU_PRIVILEGE_KEYS.map((k) => [k, set.has(k)]))
}

export function privilegesFromItems(
  items: Array<{ key?: string; permission?: string; active?: boolean }> | null | undefined,
): Record<string, boolean> {
  const out = emptyMenuPrivileges()
  for (const item of items || []) {
    const key = String(item.key || item.permission || '')
    if (key in out) out[key] = Boolean(item.active)
  }
  return out
}

/** Superadmin / support session bypasses menu privilege checks. */
export function bypassesMenuPrivileges(opts: {
  role?: string | null
  impersonating?: boolean
}): boolean {
  if (opts.impersonating) return true
  return opts.role === 'super_admin'
}

export function hasMenuPrivilege(
  privileges: Record<string, boolean> | null | undefined,
  key: string,
  opts?: { role?: string | null; impersonating?: boolean },
): boolean {
  if (opts && bypassesMenuPrivileges(opts)) return true
  return Boolean(privileges?.[key])
}

/** Whether a nav view id is allowed by the user's menu privileges. */
export function canAccessNavView(
  viewId: string,
  privileges: Record<string, boolean> | null | undefined,
  opts?: { role?: string | null; impersonating?: boolean },
): boolean {
  if (opts && bypassesMenuPrivileges(opts)) return true
  const key = NAV_ID_TO_MENU_PRIVILEGE[viewId]
  if (!key) return true
  return Boolean(privileges?.[key])
}

/**
 * Three POSTs (auth via username + session_id headers only):
 *   /users  — dropdown
 *   /get    — body: id
 *   /save   — body: id + privileges
 */
export const menuPrivilegesApi = {
  /** 1) Dropdown users — id + username */
  users: (signal?: AbortSignal) =>
    api.post<{
      ok: boolean
      users: PrivilegeDropdownUser[]
      count: number
    }>('/api/auth/menu-privileges/users', {}, { signal }),

  /** 2) Selected user's menus with active true/false */
  get: (opts: { id: number }, signal?: AbortSignal) =>
    api.post<{
      ok: boolean
      id: number | null
      user_id: number | null
      username: string
      role: string | null
      editable: boolean
      skip_grant_check?: boolean
      items: MenuPrivilegeMeta[]
    }>('/api/auth/menu-privileges/get', opts, { signal }),

  /** 3) Save active/inactive (or select_all true/false for Select All / Clear All) */
  save: (body: {
    id: number
    privileges?: Record<string, boolean>
    select_all?: boolean
  }) =>
    api.post<{
      ok: boolean
      id: number
      user_id: number
      username: string
      role?: string | null
      editable?: boolean
      skip_grant_check?: boolean
      items: MenuPrivilegeMeta[]
    }>('/api/auth/menu-privileges/save', body),

  // Back-compat aliases
  list: (signal?: AbortSignal) => menuPrivilegesApi.users(signal),
  assign: (body: { id: number; privileges: Record<string, boolean> }) =>
    menuPrivilegesApi.save(body),
  remove: (body: { id: number }) =>
    menuPrivilegesApi.save({
      id: body.id,
      privileges: emptyMenuPrivileges(),
    }),
}
