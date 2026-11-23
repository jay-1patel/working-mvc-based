import {
  Building2,
  FileText,
  HelpCircle,
  Inbox,
  MessagesSquare,
  Package,
  ShoppingCart,
  Timer,
  Users,
  AlertTriangle,
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { useTenants } from '@/lib/tenants'
import { useAsync } from '@/lib/hooks'
import { api } from '@/lib/api'
import { navigate } from '@/lib/router'
import { cn } from '@/lib/cn'
import { LoadingBlock } from '@/components/ui/feedback'
import { Panel, PrimaryButton } from '@/components/remake/ui'
import { BarChart, DonutChart, ProgressRing, SparkArea } from './charts'

interface DashboardOverview {
  days: number
  kb_files: number
  faq_files: number
  products: number
  top_questions: { query: string; count: number }[]
  total_customers: number
  total_orders: number
  orders_solved: number
  total_complaints: number
  complaints_solved: number
  total_messages: number
  unique_users: number
  avg_response_ms: number
  route_breakdown: { route: string; count: number }[]
  response_time: ResponseTimeRow[]
  frequent_questions: { query: string; count: number; last_asked?: string }[]
  total_unique_questions: number
}

interface ResponseTimeRow {
  date: string
  avg_ms: number
  count: number
}

const ROUTE_COLORS = [
  'rgb(var(--acc))',
  'rgb(var(--chip-web-ink))',
  'rgb(var(--att-ink))',
  'rgb(var(--heading))',
  'rgb(var(--bad-ink))',
  'rgb(var(--tx-muted))',
]

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

function prettyRoute(route: string | null | undefined): string {
  const r = (route || 'unknown').trim() || 'unknown'
  return r.replace(/_/g, ' ')
}

function shortDate(iso: string): string {
  try {
    const d = new Date(iso.includes('T') ? iso : `${iso}T12:00:00`)
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}

/**
 * Graphical home for every admin after login.
 * Pulls platform/tenant-scoped analytics already exposed by the backend.
 */
export function OverviewDashboard({
  mode = 'platform',
  tenantId,
}: {
  mode?: 'platform' | 'tenant'
  tenantId?: string
}) {
  const { identity } = useAuth()
  const { tenants } = useTenants()
  const tenant = tenantId ? tenants.find((t) => t.id === tenantId) : null
  const isSuper = identity?.role === 'super_admin'

  const dashboard = useAsync(
    (s) =>
      api.post<DashboardOverview>('/api/admin/dashboard/overview?days=7&limit=8', undefined, {
        signal: s,
      }),
    [],
  )

  const loading = dashboard.loading && !dashboard.data
  const ov = dashboard.data
  const st = dashboard.data
  const topQs = (dashboard.data?.frequent_questions?.length
    ? dashboard.data.frequent_questions
    : dashboard.data?.top_questions) ?? []

  const routeSlices = (ov?.route_breakdown ?? [])
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
    .map((r, i) => ({
      label: prettyRoute(r.route),
      value: r.count,
      color: ROUTE_COLORS[i % ROUTE_COLORS.length],
    }))

  const sparkPoints = (dashboard.data?.response_time ?? []).map((d) => ({
    label: shortDate(d.date),
    value: d.avg_ms,
  }))

  const metricTiles = [
    {
      icon: MessagesSquare,
      label: 'Messages (7d)',
      value: ov?.total_messages ?? '—',
      hint: 'Customer + bot turns',
    },
    {
      icon: Users,
      label: 'Unique users (7d)',
      value: ov?.unique_users ?? '—',
      hint: 'Distinct WhatsApp IDs',
    },
    {
      icon: Timer,
      label: 'Avg reply',
      value: ov ? `${Math.round(ov.avg_response_ms)} ms` : '—',
      hint: 'Outgoing webhook time',
    },
    {
      icon: Package,
      label: 'Catalogue items',
      value: st?.products ?? '—',
      hint: 'Products / offerings',
    },
    {
      icon: FileText,
      label: 'Knowledge files',
      value: st ? st.kb_files + st.faq_files : '—',
      hint: `${st?.kb_files ?? 0} KB · ${st?.faq_files ?? 0} FAQ`,
    },
    {
      icon: ShoppingCart,
      label: 'Orders',
      value: st?.total_orders ?? '—',
      hint: `${st?.orders_solved ?? 0} completed`,
    },
  ]

  return (
    <div className="dash-home">
      <section className="dash-hero mb-6">
        <div>
          <p className="text-xs font-medium text-txmuted">
            {mode === 'tenant' ? 'Tenant overview' : 'Platform overview'}
          </p>
          <h1 className="mt-2 text-xl font-semibold text-heading sm:text-2xl">
            {greeting()}, {identity?.username ?? 'there'}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-txmuted">
            {mode === 'tenant'
              ? `${tenant?.display_name || tenantId} · live pulse of chats, knowledge and fulfilment`
              : isSuper
                ? `${tenants.length} businesses · messages, routes and health across the platform`
                : 'Your WhatsApp bot at a glance'}
            {' · '}
            {new Date().toLocaleDateString(undefined, {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
            })}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {mode === 'platform' && isSuper ? (
              <>
                <PrimaryButton onClick={() => navigate('/tenants')}>
                  <Building2 className="h-4 w-4" />
                  Businesses
                </PrimaryButton>
                <button
                  type="button"
                  onClick={() => navigate('/tenant-requests')}
                  className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-3.5 py-2 text-sm font-medium text-tx transition hover:bg-paper"
                >
                  Review requests
                </button>
              </>
            ) : tenantId ? (
              <>
                <PrimaryButton onClick={() => navigate(`/tenants/${encodeURIComponent(tenantId)}/inbox`)}>
                  <Inbox className="h-4 w-4" />
                  Open chats
                </PrimaryButton>
                <button
                  type="button"
                  onClick={() => navigate(`/tenants/${encodeURIComponent(tenantId)}/uploads`)}
                  className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-3.5 py-2 text-sm font-medium text-tx transition hover:bg-paper"
                >
                  Knowledge
                </button>
              </>
            ) : null}
          </div>
        </div>
      </section>

      {loading ? (
        <LoadingBlock label="Loading overview…" />
      ) : (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {metricTiles.map((tile, i) => {
              const Icon = tile.icon
              return (
                <div
                  key={tile.label}
                  className={cn(
                    'group relative overflow-hidden rounded-panel border border-line bg-card p-4 transition hover:border-acc/30',
                    'animate-[dashFade_0.5s_ease_both]',
                  )}
                  style={{ animationDelay: `${i * 45}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium uppercase tracking-wide text-txfaint">
                        {tile.label}
                      </p>
                      <p className="mt-2 text-2xl font-bold tabular-nums tracking-tight text-tx">
                        {tile.value}
                      </p>
                      <p className="mt-1 text-xs text-txmuted">{tile.hint}</p>
                    </div>
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accsoft text-acc">
                      <Icon className="h-5 w-5" />
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <Panel title="How messages are routed">
              <p className="mb-4 text-xs text-txmuted">Last 7 days · by bot route</p>
              <DonutChart
                slices={routeSlices}
                centerLabel="turns"
                centerValue={ov?.total_messages ?? 0}
              />
            </Panel>

            <Panel title="Reply speed">
              <p className="mb-2 text-xs text-txmuted">Average outgoing response time</p>
              <SparkArea points={sparkPoints} />
            </Panel>
          </div>

          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <Panel
              title="Top questions"
              action={
                <span className="inline-flex items-center gap-1 text-xs text-txmuted">
                  <HelpCircle className="h-3.5 w-3.5" />
                  7 days
                </span>
              }
            >
              <BarChart
                items={topQs.slice(0, 8).map((q) => ({
                  label: q.query?.slice(0, 64) || '(empty)',
                  value: q.count,
                }))}
              />
            </Panel>

            <Panel title="Fulfilment health">
              <div className="grid gap-6 sm:grid-cols-2">
                <ProgressRing
                  value={st?.orders_solved ?? 0}
                  total={st?.total_orders ?? 0}
                  label="Orders completed"
                />
                <ProgressRing
                  value={st?.complaints_solved ?? 0}
                  total={st?.total_complaints ?? 0}
                  label="Complaints resolved"
                />
              </div>
              <div className="mt-6 grid grid-cols-2 gap-3 border-t border-linesoft pt-4">
                <div>
                  <p className="text-xs text-txfaint">Customers</p>
                  <p className="text-lg font-semibold tabular-nums text-tx">
                    {st?.total_customers ?? 0}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-txfaint">Open complaints</p>
                  <p className="flex items-center gap-1.5 text-lg font-semibold tabular-nums text-tx">
                    {(st?.total_complaints ?? 0) - (st?.complaints_solved ?? 0)}
                    {(st?.total_complaints ?? 0) - (st?.complaints_solved ?? 0) > 0 ? (
                      <AlertTriangle className="h-4 w-4 text-attink" />
                    ) : null}
                  </p>
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  )
}
