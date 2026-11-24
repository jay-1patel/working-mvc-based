import { useMemo, useState } from 'react'
import { AlertTriangle, Globe, MessagesSquare, Send } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { useTenants } from '@/lib/tenants'
import { usePermissions } from '@/lib/permissions'
import { useAsync } from '@/lib/hooks'
import { api } from '@/lib/api'
import { conversationsApi } from '@/lib/conversations'
import { crawlApi } from '@/lib/crawl'
import { operationsApi } from '@/lib/operations'
import { tenantApprovalsApi } from '@/lib/tenant-approvals'
import { navigate } from '@/lib/router'
import { GhostButton, NeedRow, Notice, Panel, PrimaryButton, SourceChip, StatCard } from '@/components/remake/ui'
import { LoadingBlock } from '@/components/ui/feedback'
import { OverviewDashboard } from '@/components/dashboard/overview-dashboard'
import { useToast } from '@/components/ui/toast'
import { useTenantDetail } from './hooks'

interface ErrorRow {
  created_at?: string
  message?: string
  detail?: string
  api?: string
  provider?: string
}

/**
 * A send failure, as far as the error log can tell: the Phase-1 error
 * reporter persists API/runtime errors (including failed inbox replies),
 * but there is no dedicated failed-send counter — so Today counts log
 * rows from the last hour whose text mentions sending. Rows that are
 * merely "some API failed" do not inflate this number.
 */
function isSendFailure(row: ErrorRow): boolean {
  const text = `${row.api ?? ''} ${row.provider ?? ''} ${row.message ?? ''} ${row.detail ?? ''}`.toLowerCase()
  return text.includes('send') || text.includes('/reply') || text.includes('whatsapp')
}

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super admin',
  admin: 'Admin',
  sub_admin: 'Sub admin',
}

/**
 * Today — the per-role home for a tenant's admins.
 *
 * Order is the design: what needs a person first, then the day's numbers.
 * Every figure comes from an API the console already calls (inbox,
 * chat history, crawl runs, change requests, the error log); anything a
 * call cannot supply is simply left out rather than estimated.
 */
export function TodayPanel({ tenantId }: { tenantId: string }) {
  const { identity, exitImpersonation } = useAuth()
  const { isSuperAdmin, impersonating } = usePermissions()
  const { tenants } = useTenants()
  const toast = useToast()
  const [approving, setApproving] = useState(false)
  const tenant = tenants.find((t) => t.id === tenantId) ?? null
  // View-only super admin, or customer_care after Onboarded users → Login.
  const canReviewPending = isSuperAdmin || impersonating

  const inbox = useAsync((s) => conversationsApi.inbox(tenantId, false, s), [tenantId])
  const history = useAsync(
    (s) => conversationsApi.history(tenantId, { days: 1, limit: 500 }, s),
    [tenantId],
  )
  const runs = useAsync((s) => crawlApi.listRuns(tenantId, s), [tenantId])
  const detail = useTenantDetail(tenantId)
  const mine = useAsync(
    (s) => (canReviewPending ? Promise.resolve([]) : tenantApprovalsApi.mine(s)),
    [canReviewPending],
  )
  // Pending profile / registration for this tenant — also visible in support
  // mode (Login from Onboarded users), not only view-only super-admin.
  const tenantPending = useAsync(
    (s) =>
      canReviewPending
        ? tenantApprovalsApi.allAsReviewer('pending', s).then((rows) =>
            rows.filter((r) => r.tenant_id === tenantId),
          )
        : Promise.resolve([]),
    [canReviewPending, tenantId],
  )
  const errors = useAsync(
    (s) =>
      api.post<{ count: number; errors: ErrorRow[] }>(
        `/api/admin/errors?limit=100&tenant_id=${encodeURIComponent(tenantId)}`,
        undefined,
        { signal: s },
      ),
    [tenantId],
  )
  const customers = useAsync(
    (s) => operationsApi.tenantCustomers(tenantId, { limit: 500 }, s).then((r) => r.customers),
    [tenantId],
  )

  // The latest finished crawl may be sitting staged, waiting for approval.
  const latestRun = runs.data?.history?.[0] ?? runs.data?.latest ?? null
  const staged = useAsync(
    (s) =>
      latestRun && latestRun.status === 'done'
        ? crawlApi.staged(tenantId, latestRun.id, s)
        : Promise.resolve(null),
    [latestRun?.id, latestRun?.status],
  )

  const waiting = useMemo(() => {
    const q = inbox.data
    if (!q) return null
    return q.handoff_count ?? q.queue.filter((i) => i.handover_mode === 'human').length
  }, [inbox.data])

  const turns = history.data ?? []
  const botAnswered = turns.filter((t) => t.response && t.route !== 'agent').length
  const totalTurns = turns.filter((t) => t.response).length
  const botShare = totalTurns ? Math.round((botAnswered / totalTurns) * 100) : null

  const failedSends = useMemo(() => {
    if (!errors.data) return null
    const hourAgo = Date.now() - 3_600_000
    return errors.data.errors.filter(
      (r) => isSendFailure(r) && (!r.created_at || new Date(r.created_at).getTime() >= hourAgo),
    ).length
  }, [errors.data])

  const stagedWaiting = staged.data?.status === 'staged' ? staged.data : null
  const stagedKb = stagedWaiting?.payload?.bifurcation?.knowledge_articles?.length ?? 0
  const stagedFaqs =
    stagedWaiting?.payload?.bifurcation?.faqs?.length ?? stagedWaiting?.summary?.faqs_count ?? 0

  const pendingMine = (mine.data ?? []).filter((r) => r.status === 'pending').length
  const pendingForTenant = tenantPending.data ?? []

  const todayStr = new Date().toDateString()
  const newCustomers = (customers.data ?? []).filter(
    (c) => c.first_seen && new Date(c.first_seen).toDateString() === todayStr,
  ).length

  const openReviewQueue = () => {
    if (impersonating) void exitImpersonation('/tenant-requests')
    else navigate('/tenant-requests')
  }

  /** Approve as customer_care, then leave support Login → full superadmin console. */
  const approveAndReturn = async () => {
    const target =
      pendingForTenant.find((r) => r.request_type === 'publish_profile') ?? pendingForTenant[0]
    if (!target) return
    setApproving(true)
    try {
      const result = await tenantApprovalsApi.decideAsReviewer(target.id, 'approved', '')
      toast.push(result.message ?? 'Approved and applied.')
      if (impersonating) {
        // Back to Customercare with Platform + Onboarded users (Login into any tenant).
        await exitImpersonation('/onboarding-users')
      } else {
        tenantPending.reload()
        navigate('/tenant-requests')
      }
    } catch (err) {
      toast.push((err as Error)?.message || 'Could not approve request', 'error')
    } finally {
      setApproving(false)
    }
  }

  const needs: React.ReactNode[] = []
  if (canReviewPending && pendingForTenant.length) {
    const publishCount = pendingForTenant.filter((r) => r.request_type === 'publish_profile').length
    const createCount = pendingForTenant.filter((r) => r.request_type === 'create_tenant').length
    const parts: string[] = []
    if (publishCount) {
      parts.push(
        `${publishCount} profile ${publishCount === 1 ? 'publish' : 'publishes'}`,
      )
    }
    if (createCount) {
      parts.push(
        `${createCount} registration ${createCount === 1 ? 'request' : 'requests'}`,
      )
    }
    needs.push(
      <NeedRow
        key="tenant-requests"
        icon={<Send className="h-4 w-4" />}
        action={
          <PrimaryButton onClick={openReviewQueue}>
            {impersonating ? 'Exit & review' : 'Review'}
          </PrimaryButton>
        }
      >
        <strong>{pendingForTenant.length}</strong> pending {parts.join(' and ')} for this business —
        waiting for your decision
      </NeedRow>,
    )
  }
  if (waiting) {
    needs.push(
      <NeedRow
        key="chats"
        icon={<MessagesSquare className="h-4 w-4" />}
        action={<PrimaryButton onClick={() => navigate(`/tenants/${tenantId}/inbox`)}>Open</PrimaryButton>}
      >
        <strong>{waiting}</strong> {waiting === 1 ? 'chat is' : 'chats are'} waiting for a human reply
      </NeedRow>,
    )
  }
  if (stagedWaiting) {
    needs.push(
      <NeedRow
        key="crawl"
        icon={<Globe className="h-4 w-4" />}
        action={
          <span className="flex items-center gap-2">
            <SourceChip source="web" />
            <PrimaryButton onClick={() => navigate(`/tenants/${tenantId}/website-crawler`)}>
              Review
            </PrimaryButton>
          </span>
        }
      >
        Website crawl finished — {stagedKb} knowledge items and {stagedFaqs} FAQs waiting for approval
      </NeedRow>,
    )
  }
  if (failedSends) {
    needs.push(
      <NeedRow
        key="failed"
        icon={<AlertTriangle className="h-4 w-4" />}
        action={<GhostButton onClick={() => navigate('/errors')}>Open</GhostButton>}
      >
        <strong>{failedSends}</strong> {failedSends === 1 ? 'send' : 'sends'} failed in the last hour — see
        Errors &amp; health
      </NeedRow>,
    )
  }
  if (pendingMine) {
    needs.push(
      <NeedRow
        key="requests"
        icon={<Send className="h-4 w-4" />}
        action={<GhostButton onClick={() => navigate('/tenant-requests')}>Open</GhostButton>}
      >
        <strong>{pendingMine}</strong> of your change requests {pendingMine === 1 ? 'is' : 'are'} waiting for
        super admin approval
      </NeedRow>,
    )
  }
  if (detail.data?.has_draft) {
    needs.push(
      <NeedRow
        key="draft"
        icon={<Send className="h-4 w-4" />}
        action={
          <GhostButton onClick={() => navigate(`/tenants/${tenantId}/versions`)}>Review</GhostButton>
        }
      >
        A menu/profile draft is in progress and has not been published
      </NeedRow>,
    )
  }

  const loadingCore = inbox.loading && waiting === null

  const pendingBanner =
    canReviewPending && pendingForTenant.length > 0 ? (
      <Notice tone="warn" title="Profile change awaiting your approval" className="mb-4">
        <p className="mb-3 text-sm">
          <strong>{pendingForTenant.length}</strong> pending request
          {pendingForTenant.length === 1 ? '' : 's'} for this business
          {pendingForTenant[0]?.requester_username
            ? ` (from ${pendingForTenant[0].requester_username})`
            : ''}
          . The live profile is unchanged until you approve.
        </p>
        <div className="flex flex-wrap gap-2">
          <PrimaryButton disabled={approving} onClick={() => void approveAndReturn()}>
            {approving ? 'Approving…' : 'Approve and return to superadmin'}
          </PrimaryButton>
          <GhostButton disabled={approving} onClick={openReviewQueue}>
            {impersonating ? 'Exit & review on Business requests' : 'Open Business requests'}
          </GhostButton>
        </div>
      </Notice>
    ) : null

  return (
    <div>
      {pendingBanner}
      <OverviewDashboard mode="tenant" tenantId={tenantId} />

      <Panel title="Needs you" className="mb-4">
        {loadingCore ? (
          <LoadingBlock label="Checking what needs you…" />
        ) : needs.length ? (
          <div>{needs}</div>
        ) : (
          <p className="py-1 text-sm text-txmuted">Nothing needs you right now.</p>
        )}
      </Panel>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatCard
          value={waiting ?? '—'}
          label="chats waiting for a human reply"
          tone={waiting ? 'attention' : 'normal'}
        />
        <StatCard
          value={history.loading ? '—' : botAnswered}
          label="customer messages answered by the bot today"
        />
        {failedSends !== null && (
          <StatCard
            value={failedSends}
            label="sends failed in the last hour"
            tone={failedSends > 0 ? 'failure' : 'normal'}
          />
        )}
      </div>

      <Panel title="Today so far">
        <div>
          <NeedRow>
            <span className="flex items-center justify-between">
              <span>
                {tenant?.display_name || tenantId} · {ROLE_LABELS[identity?.role ?? ''] ?? identity?.role}
              </span>
              <span className="text-xs font-normal text-txfaint">{greeting()}</span>
            </span>
          </NeedRow>
          <NeedRow>
            <span className="flex items-center justify-between">
              <span>New customers</span>
              <strong>{customers.loading ? '—' : newCustomers}</strong>
            </span>
          </NeedRow>
          <NeedRow>
            <span className="flex items-center justify-between">
              <span>Bot answered on its own</span>
              <strong>{botShare === null ? '—' : `${botShare}%`}</strong>
            </span>
          </NeedRow>
          <NeedRow>
            <span className="flex items-center justify-between">
              <span>Conversations in the inbox</span>
              <strong>{inbox.data?.count ?? inbox.data?.queue.length ?? '—'}</strong>
            </span>
          </NeedRow>
        </div>
      </Panel>
    </div>
  )
}
