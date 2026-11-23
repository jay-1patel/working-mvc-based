/**
 * The tenant sidebar, as data — remake edition.
 *
 * The remake groups the same screens by the job the admin is doing
 * (Dashboard / Talk to customers / Your business data / Grow / Manage /
 * Settings → Advanced) and renames them in plain words. Every item still
 * maps to the SAME route view it always did; only the label, the icon
 * and the grouping changed. Visibility is unchanged too: an item shows
 * when the admin's permissions and the tenant's feature flags allow it,
 * exactly as before.
 *
 * Route mapping (view id → new label):
 *   overview          → Dashboard                records   → <Products|Services|…> & prices
 *   inbox             → Chats                    website-crawler → Website crawler
 *   chat-history      → Past chats               (was: Knowledge / Website knowledge / Files)
 *   complaints        → Help requests
 *   callbacks         → Callbacks                customers → Customers
 *   menu              → Bot menu                 orders    → Orders
 *   distributors      → Partners                 campaigns → Send an offer
 *   intents           → Questions the bot understands
 *   versions          → Versions                 tokens    → Connections
 *   profile           → Profile (Advanced)       menu-edit → Menu editor (Advanced)
 *   layers            → Layers (Advanced)        api-access → API access (Advanced)
 *   chat              → Admin chat (Advanced)    test      → Test & smoke (Advanced)
 *   whatsapp-tester   → WhatsApp Tester (Advanced)
 *   projects/technologies/careers/benefits keep their names (IT tenants).
 */

import {
  AlertTriangle,
  Briefcase,
  ClipboardList,
  Cpu,
  FolderOpen,
  Gift,
  Globe,
  HelpCircle,
  History,
  Inbox,
  KeyRound,
  LayoutGrid,
  ListTree,
  Megaphone,
  Package,
  Phone,
  ScrollText,
  ShoppingCart,
  Truck,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { FeatureFlag, Features } from './types'
import { getVertical } from './verticals'

export interface NavItem {
  /** Route view id: `#/tenants/<tenant>/<id>`. */
  id: string
  label: string
  icon: LucideIcon
  /** Sidebar group heading this item sits under. */
  group: NavGroup
  /** Visible when the admin holds any of these. Undefined is ungated. */
  permissions?: string[]
  /** Visible when the tenant has this feature on. Undefined is ungated. */
  feature?: FeatureFlag
  /** True when the sidebar should show the tenant's record count. */
  showsCount?: boolean
}

export type NavGroup =
  | 'Dashboard'
  | 'Talk to customers'
  | 'Your business data'
  | 'Grow'
  | 'Manage'
  | 'Settings → Advanced'

export const NAV_GROUP_ORDER: NavGroup[] = [
  'Dashboard',
  'Talk to customers',
  'Your business data',
  'Grow',
  'Manage',
  'Settings → Advanced',
]

/**
 * Company info pages for Software & IT tenants only (tech stack, portfolio,
 * hiring, why-us). Other verticals use their own menus — banking has products /
 * eligibility, not Technologies or Careers.
 */
const IT_COMPANY_INFO_ITEMS: Omit<NavItem, 'group'>[] = [
  { id: 'projects', label: 'Projects', icon: FolderOpen, permissions: ['manage_projects'] },
  { id: 'technologies', label: 'Technologies', icon: Cpu, permissions: ['manage_technologies'] },
  { id: 'careers', label: 'Careers', icon: Briefcase, permissions: ['manage_careers'] },
  { id: 'benefits', label: 'Benefits', icon: Gift, permissions: ['manage_benefits'] },
]

/** Verticals that show the IT company-info sidebar pages. */
const VERTICALS_WITH_COMPANY_INFO = new Set(['it_software'])

/**
 * Build the sidebar for one tenant.
 *
 * `features` may be null while the resolved profile is loading (or when the
 * admin lacks `manage_operations`, which that endpoint needs). In that case the
 * feature gate is skipped and only permissions decide — showing a live inbox to
 * someone who cannot open it is a smaller sin than hiding every screen until a
 * request the user may not be allowed to make resolves.
 */
/** Tenant-nav groups only a super admin may see (hidden from admin / sub-admin). */
export const SUPER_ADMIN_ONLY_NAV_GROUPS: NavGroup[] = ['Grow', 'Manage']

/**
 * Route view ids only a super admin may see. Includes Grow/Manage screens,
 * Past chats / Help requests / Callbacks, and Models|Products & prices.
 */
export const SUPER_ADMIN_ONLY_VIEWS = [
  'campaigns',
  'intents',
  'versions',
  'tokens',
  'chat-history',
  'complaints',
  'callbacks',
  'records',
  'offerings',
] as const

export function buildTenantNav(opts: {
  vertical?: string | null
  features?: Features | null
  can: (permission: string) => boolean
  /**
   * When explicitly `false` (company admin / sub-admin), super-admin-only
   * groups and views are omitted. Super admins keep them. Omit / `true` /
   * `undefined` keeps the full list (used by `knownViews` and unit tests
   * that do not pass a role).
   */
  isSuperAdmin?: boolean
}): NavItem[] {
  const content = getVertical(opts.vertical).content
  const features = opts.features ?? null
  const companyInfo = VERTICALS_WITH_COMPANY_INFO.has(opts.vertical ?? '')
    ? IT_COMPANY_INFO_ITEMS.map((item) => ({ ...item, group: 'Your business data' as NavGroup }))
    : []

  const uploadPermissions = ['upload_faq', 'upload_kb', 'view_files', 'catalogue_new_arrival']
  const hideSuperAdminOnly = opts.isSuperAdmin === false

  const items: NavItem[] = [
    { id: 'overview', label: 'Dashboard', icon: LayoutGrid, group: 'Dashboard' },

    // Talk to customers
    {
      id: 'inbox',
      label: 'Chats',
      icon: Inbox,
      group: 'Talk to customers',
      permissions: ['view_inbox'],
    },
    {
      id: 'chat-history',
      label: 'Past chats',
      icon: History,
      group: 'Talk to customers',
      permissions: ['chat_history'],
    },
    {
      id: 'complaints',
      label: 'Help requests',
      icon: AlertTriangle,
      group: 'Talk to customers',
      permissions: ['view_complaints'],
      feature: 'complaints',
    },
    {
      id: 'callbacks',
      label: 'Callbacks',
      icon: Phone,
      group: 'Talk to customers',
      permissions: ['manage_operations'],
      feature: 'callback',
      showsCount: true,
    },

    // Your business data
    { id: 'menu', label: 'Bot menu', icon: ListTree, group: 'Your business data', permissions: ['manage_operations'] },
    {
      id: 'records',
      label: `${content.label} & prices`,
      icon: Package,
      group: 'Your business data',
      permissions: ['view_products'],
      feature: 'offerings',
      showsCount: true,
    },
    {
      // One door for crawl + document knowledge + raw files (was three
      // sidebar entries: Knowledge, Website knowledge, Files).
      id: 'website-crawler',
      label: 'Website crawler',
      icon: Globe,
      group: 'Your business data',
      permissions: uploadPermissions,
    },
    ...companyInfo,
    { id: 'customers', label: 'Customers', icon: Users, group: 'Your business data', permissions: ['view_customers'] },
    {
      id: 'orders',
      label: 'Orders',
      icon: ShoppingCart,
      group: 'Your business data',
      permissions: ['view_orders'],
      feature: 'orders',
    },
    {
      id: 'distributors',
      label: 'Partners',
      icon: Truck,
      group: 'Your business data',
      permissions: ['view_distributors'],
      feature: 'distributors',
    },

    // Grow
    {
      id: 'campaigns',
      label: 'Send an offer',
      icon: Megaphone,
      group: 'Grow',
      permissions: ['view_campaigns'],
      feature: 'campaigns',
    },
    {
      id: 'intents',
      label: 'Questions the bot understands',
      icon: HelpCircle,
      group: 'Grow',
      permissions: ['manage_operations'],
    },

    // Manage
    { id: 'versions', label: 'Versions', icon: ClipboardList, group: 'Manage', permissions: ['manage_operations'] },
    { id: 'tokens', label: 'Connections', icon: KeyRound, group: 'Manage', permissions: ['manage_operations'] },

    // Settings → Advanced: the technical screens, kept reachable but out
    // of the daily path.
    { id: 'profile', label: 'Profile', icon: ScrollText, group: 'Settings → Advanced', permissions: ['manage_operations'] },
    // The remaining advanced tools still have routes and implementations, but
    // are intentionally hidden from the admin panel for now.
  ]
  return items.filter((item) => {
    if (
      hideSuperAdminOnly &&
      (SUPER_ADMIN_ONLY_NAV_GROUPS.includes(item.group) ||
        (SUPER_ADMIN_ONLY_VIEWS as readonly string[]).includes(item.id))
    ) {
      return false
    }
    return isVisible(item, opts.can, features)
  })
}

/** Whether one item passes its permission and feature gates. */
export function isVisible(
  item: NavItem,
  can: (permission: string) => boolean,
  features: Features | null,
): boolean {
  if (item.permissions && !item.permissions.some((p) => can(p))) return false
  if (item.feature && features && features[item.feature] === false) return false
  return true
}

/** The ids a known view can resolve to — used to decide "unknown view". */
export function knownViews(vertical?: string | null): string[] {
  return buildTenantNav({ vertical, features: null, can: () => true }).map((i) => i.id)
}
