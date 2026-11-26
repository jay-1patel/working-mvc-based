import { AuthProvider, useAuth } from '@/lib/auth'
import { TenantProvider, useTenants } from '@/lib/tenants'
import { isOnboardingLocked, usePermissions } from '@/lib/permissions'
import { SUPER_ADMIN_ONLY_VIEWS } from '@/lib/navigation'
import { parseRoute, useRoute } from '@/lib/router'
import { ToastProvider } from '@/components/ui/toast'
import { ConfirmProvider } from '@/components/ui/confirm'
import { LoginView } from '@/components/auth/login-view'
import { AppShell } from '@/components/layout/app-shell'
import { PageHeader } from '@/components/layout/page-header'
import { LoadingBlock } from '@/components/ui/feedback'
import { Notice } from '@/components/remake/ui'
import { Button } from '@/components/ui/button'
import { TenantList } from '@/components/tenants/tenant-list'
import { ProfileEditor } from '@/components/tenants/profile-editor'
import { BotMenuPanel } from '@/components/tenants/bot-menu-panel'
import { TodayPanel } from '@/components/tenants/today-panel'
import { SuperToday } from '@/components/tenants/super-today'
import { OverviewDashboard } from '@/components/dashboard/overview-dashboard'
import { ChatsPanel } from '@/components/tenants/chats-panel'
import { MenuEditor } from '@/components/tenants/menu-editor'
import { OfferingsPanel } from '@/components/tenants/offerings-panel'
import { RecordsPanel } from '@/components/tenants/records-panel'
import { CustomersPanel } from '@/components/tenants/customers-panel'
import { OrdersPanel } from '@/components/tenants/orders-panel'
import { CampaignsPanel } from '@/components/tenants/campaigns-panel'
import { DistributorsPanel } from '@/components/tenants/distributors-panel'
import { ChatHistoryPanel } from '@/components/tenants/chat-history-panel'
import { CallbacksPanel } from '@/components/tenants/callbacks-panel'
import { ComplaintsPanel } from '@/components/tenants/complaints-panel'
import { WebsiteCrawlerPanel } from '@/components/tenants/website-crawler-panel'
import { SettingsPanel } from '@/components/tenants/settings-panel'
import { AdminChatPanel } from '@/components/tenants/admin-chat'

import { IntentsEditor } from '@/components/tenants/intents-editor'
import { InfoPagePanel } from '@/components/tenants/info-page-panel'
import { VersionsPanel } from '@/components/tenants/versions-panel'
import { LayersPanel } from '@/components/tenants/layers-panel'
import { TokensPanel } from '@/components/tenants/tokens-panel'
import { TestAndSmoke } from '@/components/tenants/test-and-smoke'
import { WhatsAppTester } from '@/components/tester/whatsapp-tester'
import { TeamScreen } from '@/components/team/team-screen'
import { OnboardingUsersPanel } from '@/components/team/onboarding-users'
import { PrivilegesPanel } from '@/components/team/privileges-panel'
import { isCustomerCareIdentity } from '@/lib/admins'
import { canAccessNavView, NAV_ID_TO_MENU_PRIVILEGE } from '@/lib/menu-privileges'
import { RegisterWizard } from '@/components/onboarding/register-wizard'
import { ApiOnboardingPanel } from '@/components/tenants/api-onboarding-panel'
import { ApiOnboardingReview } from '@/components/team/api-onboarding-review'
import { AuditHistory } from '@/components/team/audit-history'
import { ErrorsPanel } from '@/components/team/errors-panel'
import { TenantChangeReview, MyTenantChangeRequests } from '@/components/tenants/tenant-approvals-panel'

function Router() {
  const route = parseRoute(useRoute())
  const { canManageTenants, canManageTeam, isSuperAdmin, can, impersonating } = usePermissions()
  const { identity } = useAuth()
  const locked = isOnboardingLocked(identity, { impersonating })

  // customer_care: home is Onboarded users + Privileges. Full superadmin
  // tools unlock only after Login into a tenant (support session).
  if (
    isCustomerCareIdentity(identity) &&
    !impersonating &&
    route.view !== 'onboarding-users' &&
    route.view !== 'privileges'
  ) {
    return (
      <AppShell route={{ ...route, tenantId: null, view: 'onboarding-users' }}>
        <OnboardingUsersPanel />
      </AppShell>
    )
  }

  // First-login lock: admin with no tenant_id must finish WhatsApp → company
  // setup before the console opens. Drop any stale tenantId from the URL so
  // chrome does not poll inbox / tenant APIs against an unbound session.
  if (locked) {
    return (
      <AppShell route={{ ...route, tenantId: null, view: 'register' }}>
        <RegisterWizard />
      </AppShell>
    )
  }

  if (route.view === 'dashboard') {
    // Graphical home. Tenant admins with a bound company jump into that
    // tenant's Today view (same charts + operational needs).
    if (!isSuperAdmin && identity?.tenant_id) {
      return (
        <AppShell route={{ ...route, tenantId: identity.tenant_id, view: 'overview' }}>
          <TodayPanel tenantId={identity.tenant_id} />
        </AppShell>
      )
    }
    return (
      <AppShell route={route}>
        {isSuperAdmin ? <SuperToday /> : <OverviewDashboard mode="platform" />}
      </AppShell>
    )
  }

  if (route.view === 'register') {
    // First-login setup for company admins; super admins see provisioning guidance.
    if (!canManageTenants && identity?.role !== 'admin') return <NotPermitted what="set up a tenant" />
    return (
      <AppShell route={route}>
        <RegisterWizard />
      </AppShell>
    )
  }

  if (route.view === 'tenant-requests') {
    if (isSuperAdmin) {
      return (
        <AppShell route={route}>
          <TenantChangeReview />
        </AppShell>
      )
    }
    if (identity && (identity.role === 'admin' || identity.role === 'sub_admin') && canManageTenants) {
      return (
        <AppShell route={route}>
          <MyTenantChangeRequests />
        </AppShell>
      )
    }
    return <NotPermitted what="view tenant change requests" />
  }

  if (route.view === 'team') {
    if (!canManageTeam && !impersonating) {
      return <NotPermitted what="manage the team" permission="manage_admins" />
    }
    return (
      <AppShell route={route}>
        <TeamScreen />
      </AppShell>
    )
  }

  if (route.view === 'onboarding-users') {
    if (!isCustomerCareIdentity(identity)) {
      return <NotPermitted what="open onboarding users" />
    }
    return (
      <AppShell route={route}>
        <OnboardingUsersPanel />
      </AppShell>
    )
  }

  if (route.view === 'privileges') {
    // Hard-coded superadmin-only — never grantable via the privilege table.
    if (!isSuperAdmin || impersonating) {
      return <NotPermitted what="manage menu privileges" permission="super admin" />
    }
    return (
      <AppShell route={route}>
        <PrivilegesPanel />
      </AppShell>
    )
  }

  if (route.view === 'api-requests') {
    if (!isSuperAdmin) return <NotPermitted what="review API access requests" permission="super admin" />
    return (
      <AppShell route={route}>
        <ApiOnboardingReview />
      </AppShell>
    )
  }

  if (route.view === 'audit-history') {
    // Super admins see every tenant; a tenant admin sees only their own
    // tenant's activity (the page and the API both enforce that scope).
    if (!isSuperAdmin && identity?.role !== 'admin' && !impersonating) {
      return <NotPermitted what="view audit history" />
    }
    return (
      <AppShell route={route}>
        <AuditHistory />
      </AppShell>
    )
  }

  if (route.view === 'errors') {
    if (!isSuperAdmin && identity?.role !== 'admin' && !impersonating) {
      return <NotPermitted what="view errors" />
    }
    return (
      <AppShell route={route}>
        <ErrorsPanel />
      </AppShell>
    )
  }

  if (!route.tenantId) {
    // Empty / unknown global routes: show the graphical overview for
    // super admins; tenant admins without a selected company get the list.
    return (
      <AppShell route={route}>
        {isSuperAdmin ? <SuperToday /> : <TenantList />}
      </AppShell>
    )
  }

  const writeViews = new Set(['profile', 'profile-menu', 'menu-edit', 'versions', 'tokens'])
  if (route.view === 'api-access') {
    if (!isSuperAdmin && (!identity?.tenant_id || route.tenantId !== identity.tenant_id || !can('manage_operations'))) {
      return <AppShell route={route}><NotPermitted what="request API access for this tenant" /></AppShell>
    }
    return (
      <AppShell route={route}>
        <ApiOnboardingPanel />
      </AppShell>
    )
  }

  // Super-admin-only tenant screens (Grow/Manage, Past chats / Help
  // requests / Callbacks, Models|Products & prices, Layers / Test & smoke /
  // WhatsApp Tester) — company admins and sub-admins do not see them.
  // customer_care support sessions may open every screen.
  if (
    (SUPER_ADMIN_ONLY_VIEWS as readonly string[]).includes(route.view) &&
    !isSuperAdmin &&
    !impersonating
  ) {
    return (
      <AppShell route={route}>
        <NotPermitted what="open this screen" permission="super admin" />
      </AppShell>
    )
  }

  // Menu privilege gate (deep links): first-time users with no grants cannot
  // open tagged screens until a superadmin assigns them on Privileges.
  if (
    route.tenantId &&
    NAV_ID_TO_MENU_PRIVILEGE[route.view] &&
    !canAccessNavView(route.view, identity?.menu_privileges, {
      role: identity?.role,
      impersonating,
    })
  ) {
    return (
      <AppShell route={route}>
        <NotPermitted
          what="open this menu page"
          permission={`menu privilege (${NAV_ID_TO_MENU_PRIVILEGE[route.view]})`}
        />
      </AppShell>
    )
  }

  if (writeViews.has(route.view) && !canManageTenants && !impersonating) {
    return (
      <AppShell route={route}>
        <NotPermitted what="change tenant configuration" />
      </AppShell>
    )
  }

  return (
    <AppShell route={route}>
      {route.view === 'overview' && <TodayPanel tenantId={route.tenantId} />}
      {route.view === 'profile' && <ProfileEditor tenantId={route.tenantId} mode="brand" />}
      {route.view === 'profile-menu' && <ProfileEditor tenantId={route.tenantId} mode="menu" />}
      {route.view === 'menu' && <BotMenuPanel tenantId={route.tenantId} />}
      {route.view === 'settings' && <SettingsPanel tenantId={route.tenantId} />}
      {route.view === 'menu-edit' && (
        <MenuEditor tenantId={route.tenantId} focusId={route.query.get('focus')} />
      )}
      {route.view === 'intents' && <IntentsEditor tenantId={route.tenantId} />}
      {route.view === 'records' && <RecordsPanel tenantId={route.tenantId} />}
      {route.view === 'customers' && <CustomersPanel tenantId={route.tenantId} />}
      {route.view === 'orders' && <OrdersPanel tenantId={route.tenantId} />}
      {route.view === 'campaigns' && <CampaignsPanel tenantId={route.tenantId} />}
      {route.view === 'distributors' && <DistributorsPanel tenantId={route.tenantId} />}
      {route.view === 'offerings' && <OfferingsPanel tenantId={route.tenantId} />}
      {route.view === 'projects' && <InfoPagePanel tenantId={route.tenantId} page="projects" />}
      {route.view === 'chat-history' && <ChatHistoryPanel tenantId={route.tenantId} />}
      {route.view === 'inbox' && <ChatsPanel tenantId={route.tenantId} />}
      {route.view === 'complaints' && <ComplaintsPanel tenantId={route.tenantId} />}
      {route.view === 'callbacks' && <CallbacksPanel tenantId={route.tenantId} />}
      {(route.view === 'website-crawler' ||
        route.view === 'uploads' ||
        route.view === 'website-knowledge') && (
        <WebsiteCrawlerPanel
          key={route.view === 'uploads' ? 'files' : 'crawl'}
          tenantId={route.tenantId}
          initialTab={route.view === 'uploads' ? 'files' : 'crawl'}
        />
      )}
      {route.view === 'chat' && <AdminChatPanel tenantId={route.tenantId} />}
      {route.view === 'versions' && <VersionsPanel tenantId={route.tenantId} />}
      {route.view === 'layers' && <LayersPanel tenantId={route.tenantId} />}
      {route.view === 'tokens' && <TokensPanel tenantId={route.tenantId} />}
      {route.view === 'test' && <TestAndSmoke tenantId={route.tenantId} />}
      {route.view === 'whatsapp-tester' && <WhatsAppTester tenantId={route.tenantId} />}
      {PENDING_VIEWS.has(route.view) && <ComingSoon view={route.view} />}
      {!KNOWN_VIEWS.includes(route.view) && (
        <Notice tone="warn" title="Unknown view">
          <code>{route.view}</code> is not a screen in this console.
        </Notice>
      )}
    </AppShell>
  )
}

/**
 * Views the sidebar advertises before their screens are built. Keeping them
 * listed (rather than hidden) is deliberate: the navigation is the contract,
 * and a dead link with an honest label beats a silently missing capability.
 * Of the IT company-info pages only Projects has its panel; Technologies,
 * Careers, Benefits and Portfolio are still to come. The standalone
 * callback-detail route is also not built — the Callbacks panel handles
 * detail inline.
 */
const PENDING_VIEWS = new Set<string>([
  'callback',
  'portfolio',
  'technologies',
  'careers',
  'benefits',
])

const KNOWN_VIEWS = [
  'overview',
  'profile',
  'profile-menu',
  'menu',
  'settings',
  'menu-edit',
  'intents',
  'records',
  'offerings',
  'customers',
  'orders',
  'campaigns',
  'distributors',
  'projects',
  'portfolio',
  'technologies',
  'careers',
  'benefits',
  'website-crawler',
  'uploads',
  'website-knowledge',
  'chat',
  'chat-history',
  'inbox',
  'complaints',
  'versions',
  'layers',
  'tokens',
  'test',
  'whatsapp-tester',
  'callbacks',
  'callback',
  'api-access',
  'dashboard',
  'tenant-requests',
  'onboarding-users',
  'api-requests',
  'audit-history',
  'errors',
]

function ComingSoon({ view }: { view: string }) {
  const label = view.replace(/-/g, ' ')
  return (
    <div>
      <PageHeader title={label.replace(/\b\w/g, (c) => c.toUpperCase())} />
      <Notice tone="info" title="Coming next">
        This screen is wired into the navigation but its panel is not built yet.
      </Notice>
    </div>
  )
}

function NotPermitted({ what, permission = 'manage_operations' }: { what: string; permission?: string }) {
  return (
    <div className="mx-auto max-w-lg py-16">
      <Notice tone="warn" title="Not permitted">
        Your account cannot {what}. This screen needs the{' '}
        <strong>{permission}</strong> permission — a super admin can grant it under Team &amp; permissions.
      </Notice>
    </div>
  )
}

function AuthedApp() {
  const { loading, identity } = useAuth()
  const { tenants, loading: tenantsLoading, error, reload } = useTenants()
  const route = parseRoute(useRoute())
  const { canManageTeam } = usePermissions()

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingBlock label="Connecting to the backend…" />
      </div>
    )
  }

  if (!identity) return <LoginView />

  // The tenant registry needs manage_operations. Without it, skip it and let
  // the admin work inside the team screen (or sign in as someone who can).
  if (error && canManageTeam && route.view !== 'team') {
    return (
      <div className="mx-auto max-w-lg px-6 py-20">
        <Notice tone="bad" title="Cannot list tenants">
          {error}
        </Notice>
        <Button className="mt-4" onClick={reload}>
          Retry
        </Button>
      </div>
    )
  }

  if (tenantsLoading && !tenants.length && route.view !== 'register' && error) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingBlock label="Loading tenants…" />
      </div>
    )
  }

  // A company admin stays in onboarding until a super admin approves one of
  // the change requests they filed; `Router` applies that lock. Hold on the
  // tenant list load so the lock does not flash before data settles.
  if (identity?.role === 'admin' && tenantsLoading && !tenants.length) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingBlock label="Loading tenants…" />
      </div>
    )
  }

  return <Router />
}

export default function App() {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <AuthProvider>
          <TenantProvider>
            <div className="h-full">
              <AuthedApp />
            </div>
          </TenantProvider>
        </AuthProvider>
      </ConfirmProvider>
    </ToastProvider>
  )
}