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
 *   menu              → WhatsApp menu (under WhatsApp dropdown)
 *   profile-menu      → Profile menu (hours + notifications, under WhatsApp dropdown)
 *   settings          → Settings (customer KB gaps / unanswered queries, under WhatsApp dropdown)
 *   distributors      → Partners                 campaigns → Send an offer
 *   intents           → Questions the bot understands
 *   versions          → Versions                 tokens    → Connections
 *   profile           → Profile (below Chats; brand only)
 *   menu-edit         → Menu editor (Advanced)
 *   layers            → Layers (Advanced)        api-access → API access (Advanced)
 *   chat              → Admin chat (Advanced)    test      → Test & smoke (Advanced)
 *   whatsapp-tester   → WhatsApp Tester (Advanced)
 *   projects/technologies/careers/benefits keep their names (IT tenants).
 */

import {
  AlertTriangle,
  Briefcase,
  ClipboardList,
  Clock,
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
  MessageCircle,
  Package,
  Phone,
  ScrollText,
  Settings,
  ShoppingCart,
  Truck,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { FeatureFlag, Features } from './types'
import { getVertical } from './verticals'

export interface NavChild {
  /** Route view id: `#/tenants/<tenant>/<id>`. */
  id: string
  label: string
  icon: LucideIcon
  /** Visible when the admin holds any of these. Undefined is ungated. */
  permissions?: string[]
  /** Visible when the tenant has this feature on. Undefined is ungated. */
  feature?: FeatureFlag
  /**
   * Menu privilege key from the privilege table. When set, the item is
   * hidden until a superadmin grants that key (superadmin / support bypass).
   */
  menuPrivilege?: string
}

export interface NavItem {
  /**
   * Route view id: `#/tenants/<tenant>/<id>`.
   * For dropdown parents this is a sidebar key only (not a route).
   */
  id: string
  label: string
  icon: LucideIcon
  /** Sidebar group heading this item sits under. */
  group: NavGroup
  /** Visible when the admin holds any of these. Undefined is ungated. */
  permissions?: string[]
  /** Visible when the tenant has this feature on. Undefined is ungated. */
  feature?: FeatureFlag
  /**
   * Menu privilege key from the privilege table. When set, the item is
   * hidden until a superadmin grants that key (superadmin / support bypass).
   */
  menuPrivilege?: string
  /** True when the sidebar should show the tenant's record count. */
  showsCount?: boolean
  /** Nested items rendered as a sidebar dropdown under this parent. */
  children?: NavChild[]
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
 * `features` may be null while the resolved profile is loading or unavailable.
 * Feature-gated items fail closed; ungated items remain permission-driven.
 */
/** Tenant-nav groups only a super admin may see (hidden from admin / sub-admin). */
export const SUPER_ADMIN_ONLY_NAV_GROUPS: NavGroup[] = ['Grow', 'Manage']

/**
 * Route view ids only a super admin may see. Includes Grow/Manage screens,
 * Past chats / Help requests / Callbacks, Models|Products & prices, and
 * Layers / Test & smoke / WhatsApp Tester under Settings → Advanced.
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
  'layers',
  'test',
  'whatsapp-tester',
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
  /**
   * Menu privilege grants. When provided (and not bypassed), items tagged
   * with `menuPrivilege` stay hidden until that key is true. Superadmin /
   * support Login pass `bypassMenuPrivileges: true`.
   */
  menuPrivileges?: Record<string, boolean> | null
  /** When true, skip menu-privilege gating (superadmin / support). */
  bypassMenuPrivileges?: boolean
}): NavItem[] {
  const content = getVertical(opts.vertical).content
  const features = opts.features ?? null
  const companyInfo = VERTICALS_WITH_COMPANY_INFO.has(opts.vertical ?? '')
    ? IT_COMPANY_INFO_ITEMS.map((item) => ({ ...item, group: 'Your business data' as NavGroup }))
    : []

  const uploadPermissions = ['upload_faq', 'upload_kb', 'view_files', 'catalogue_new_arrival']
  const hideSuperAdminOnly = opts.isSuperAdmin === false
  const bypassMenu = Boolean(opts.bypassMenuPrivileges)
  const menuPrivileges = opts.menuPrivileges ?? null

  const items: NavItem[] = [
    {
      id: 'overview',
      label: 'Dashboard',
      icon: LayoutGrid,
      group: 'Dashboard',
      menuPrivilege: 'graphic',
    },

    // Talk to customers
    {
      id: 'inbox',
      label: 'Chats',
      icon: Inbox,
      group: 'Talk to customers',
      permissions: ['view_inbox'],
      menuPrivilege: 'chats',
    },
    {
      id: 'profile',
      label: 'Profile',
      icon: ScrollText,
      group: 'Talk to customers',
      permissions: ['manage_operations'],
      menuPrivilege: 'profile',
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

    // Your business data — company console core:
    // WhatsApp dropdown → Website crawler → Customers
    {
      id: 'whatsapp',
      label: 'WhatsApp',
      icon: MessageCircle,
      group: 'Your business data',
      permissions: ['manage_operations'],
      children: [
        {
          id: 'menu',
          label: 'WhatsApp menu',
          icon: ListTree,
          permissions: ['manage_operations'],
          menuPrivilege: 'menu',
        },
        {
          id: 'profile-menu',
          label: 'Profile menu',
          icon: Clock,
          permissions: ['manage_operations'],
          menuPrivilege: 'setup_chatbot',
        },
        {
          id: 'settings',
          label: 'Settings',
          icon: Settings,
          permissions: ['manage_operations'],
          menuPrivilege: 'setup_chatbot',
        },
      ],
    },
    {
      // One door for crawl + document knowledge + raw files (was three
      // sidebar entries: Knowledge, Website knowledge, Files).
      id: 'website-crawler',
      label: 'Website crawler',
      icon: Globe,
      group: 'Your business data',
      permissions: uploadPermissions,
      menuPrivilege: 'website_crawler',
    },
    {
      id: 'customers',
      label: 'Customers',
      icon: Users,
      group: 'Your business data',
      permissions: ['view_customers'],
      menuPrivilege: 'customer',
    },
    {
      id: 'records',
      label: `${content.label} & prices`,
      icon: Package,
      group: 'Your business data',
      permissions: ['view_products'],
      feature: 'offerings',
      showsCount: true,
    },
    ...companyInfo,
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

    // Settings → Advanced tools still have routes and implementations, but
    // are intentionally hidden from the admin panel for now.
  ]
  return items
    .map((item) => {
      if (!item.children?.length) return item
      return {
        ...item,
        children: item.children.filter((child) =>
          isVisible(child, opts.can, features, menuPrivileges, bypassMenu),
        ),
      }
    })
    .filter((item) => {
      if (
        hideSuperAdminOnly &&
        (SUPER_ADMIN_ONLY_NAV_GROUPS.includes(item.group) ||
          (SUPER_ADMIN_ONLY_VIEWS as readonly string[]).includes(item.id))
      ) {
        return false
      }
      if (item.children) {
        return item.children.length > 0 && isVisible(item, opts.can, features, menuPrivileges, bypassMenu)
      }
      return isVisible(item, opts.can, features, menuPrivileges, bypassMenu)
    })
}

/** Whether one item passes its permission, feature, and menu-privilege gates. */
export function isVisible(
  item: Pick<NavItem, 'permissions' | 'feature' | 'menuPrivilege'>,
  can: (permission: string) => boolean,
  features: Features | null,
  menuPrivileges: Record<string, boolean> | null = null,
  bypassMenuPrivileges = false,
): boolean {
  if (item.permissions && !item.permissions.some((p) => can(p))) return false
  if (item.feature && (!features || features[item.feature] !== true)) return false
  // Fail closed only when a privileges map was provided (null/omit = ungated,
  // used by knownViews / unit tests that do not load grants).
  if (!bypassMenuPrivileges && item.menuPrivilege && menuPrivileges) {
    if (!menuPrivileges[item.menuPrivilege]) return false
  }
  return true
}

/** The ids a known view can resolve to — used to decide "unknown view". */
export function knownViews(vertical?: string | null): string[] {
  return buildTenantNav({ vertical, features: null, can: () => true }).flatMap((item) =>
    item.children?.length ? item.children.map((child) => child.id) : [item.id],
  )
}
