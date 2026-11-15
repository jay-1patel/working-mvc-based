import { ClipboardCheck, ShieldCheck, Building2 } from 'lucide-react'
import { useTenants } from '@/lib/tenants'
import { useAsync } from '@/lib/hooks'
import { tenantApprovalsApi } from '@/lib/tenant-approvals'
import { apiOnboarding } from '@/lib/api-onboarding'
import { navigate } from '@/lib/router'
import { NeedRow, Panel, PrimaryButton } from '@/components/remake/ui'
import { OverviewDashboard } from '@/components/dashboard/overview-dashboard'
import { TenantList } from './tenant-list'

/**
 * Super admin home: graphical platform overview first, then approvals
 * and the business list.
 */
export function SuperToday() {
  const { tenants } = useTenants()

  const changeRequests = useAsync((s) => tenantApprovalsApi.all('pending', s), [])
  const apiRequests = useAsync((s) => apiOnboarding.all('pending', s), [])

  const pendingChanges = changeRequests.data ?? []
  const pendingApis = apiRequests.data ?? []
  const needingAttention = tenants.filter((t) => !t.current_version || (t.status && t.status !== 'active'))

  const needs: React.ReactNode[] = []
  if (pendingChanges.length) {
    needs.push(
      <NeedRow
        key="changes"
        icon={<ClipboardCheck className="h-4 w-4" />}
        action={<PrimaryButton onClick={() => navigate('/tenant-requests')}>Review</PrimaryButton>}
      >
        <strong>{pendingChanges.length}</strong> business{' '}
        {pendingChanges.length === 1 ? 'request is' : 'requests are'} waiting for your decision
      </NeedRow>,
    )
  }
  if (pendingApis.length) {
    needs.push(
      <NeedRow
        key="apis"
        icon={<ShieldCheck className="h-4 w-4" />}
        action={<PrimaryButton onClick={() => navigate('/api-requests')}>Review</PrimaryButton>}
      >
        <strong>{pendingApis.length}</strong> API access{' '}
        {pendingApis.length === 1 ? 'request is' : 'requests are'} waiting for your decision
      </NeedRow>,
    )
  }
  if (needingAttention.length) {
    needs.push(
      <NeedRow key="health" icon={<Building2 className="h-4 w-4" />}>
        <strong>{needingAttention.length}</strong>{' '}
        {needingAttention.length === 1 ? 'business has' : 'businesses have'} no published version or an
        inactive status — see Data health below
      </NeedRow>,
    )
  }

  return (
    <div>
      <OverviewDashboard mode="platform" />

      <Panel title="Needs you" className="mb-4">
        {changeRequests.loading || apiRequests.loading ? (
          <p className="py-1 text-sm text-txmuted">Checking the approval queues…</p>
        ) : needs.length ? (
          <div>{needs}</div>
        ) : (
          <p className="py-1 text-sm text-txmuted">Nothing needs you right now.</p>
        )}
      </Panel>

      <TenantList />
    </div>
  )
}
