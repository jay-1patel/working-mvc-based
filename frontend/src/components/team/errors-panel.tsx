import { useEffect, useState } from 'react'
import { Check, Copy, Download, RefreshCw, Search } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useAsync } from '@/lib/hooks'
import { formatDate } from '@/lib/format'
import { Card, EmptyState, ErrorBanner, GhostButton, Pill, FieldInput, FieldSelect, PrimaryButton } from '@/components/remake/ui'
import { LoadingBlock } from '@/components/ui/feedback'
import { PageHeader } from '@/components/layout/page-header'

interface ApiErrorRow {
  id: number
  created_at?: string
  provider?: string
  api?: string
  severity?: string
  message?: string
  detail?: string
  tenant_id?: string | null
  request_id?: string | null
  http_status?: number | null
}

/** The request id, with a one-click copy — this is the id support quotes. */
function RequestId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable — the id stays visible to copy by hand */
    }
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      Request: <code className="font-mono text-tx">{value}</code>
      <button
        type="button"
        onClick={copy}
        className="inline-flex items-center gap-1 rounded-md border border-line bg-card px-1.5 py-0.5 font-medium text-tx transition hover:bg-paper"
      >
        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        {copied ? 'Copied' : 'Copy'}
      </button>
    </span>
  )
}

/**
 * Read-only view of the persisted API/runtime errors (Phase 1 error
 * reporter). Super admins see every tenant; a tenant admin is scoped to
 * their own tenant — the server forces that scope, the tenant filter here
 * just makes it explicit. There are no actions on this page by design.
 */
export function ErrorsPanel() {
  const { identity } = useAuth()
  const scopedTenant = identity?.role === 'admin' ? identity.tenant_id ?? null : null
  const [offset, setOffset] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const emptyFilters = { search: '', provider: '', tenant: '', severity: '', status: '', since: '', until: '' }
  const [draft, setDraft] = useState(emptyFilters)
  const [filters, setFilters] = useState(emptyFilters)
  const pageSize = 50
  const query = new URLSearchParams({ limit: String(pageSize), offset: String(offset) })
  if (scopedTenant || filters.tenant) query.set('tenant_id', scopedTenant || filters.tenant)
  if (filters.search) query.set('search', filters.search)
  if (filters.provider) query.set('provider', filters.provider)
  if (filters.severity) query.set('severity', filters.severity)
  if (filters.status) query.set('http_status', filters.status)
  if (filters.since) query.set('since', new Date(`${filters.since}T00:00:00`).toISOString())
  if (filters.until) query.set('until', new Date(`${filters.until}T23:59:59.999`).toISOString())
  const queryString = query.toString()
  const state = useAsync(
    (signal) =>
      api.get<{ count: number; total?: number; has_more?: boolean; errors: ApiErrorRow[] }>(
        `/api/admin/errors?${queryString}`,
        signal,
      ),
    [queryString],
  )
  const rows = state.data?.errors ?? []
  const total = state.data?.total ?? state.data?.count ?? 0
  useEffect(() => { if (state.data) setUpdatedAt(new Date().toISOString()) }, [state.data])
  useEffect(() => {
    if (!autoRefresh || state.loading) return
    const timer = window.setInterval(() => { if (!document.hidden) state.reload() }, 15_000)
    return () => window.clearInterval(timer)
  }, [autoRefresh, state.loading, state.reload])
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = 'ai-chatbot-errors-page.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Errors & health"
        description={
          scopedTenant
            ? 'API, service, and browser failures for your tenant. Use a request ID to trace related events.'
            : 'API, service, and browser failures across all tenants. Use a request ID to trace related events.'
        }
        actions={
          <><GhostButton onClick={download} disabled={!rows.length}><Download className="h-4 w-4" />Download page</GhostButton><GhostButton onClick={state.reload} disabled={state.loading}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </GhostButton></>
        }
      />
      <Card className="p-4">
        <form onSubmit={(event) => { event.preventDefault(); setOffset(0); setFilters({ ...draft }) }}>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <FieldInput label="Search logs" placeholder="Request ID, API, or message" maxLength={200} value={draft.search} onChange={(e) => setDraft({ ...draft, search: e.target.value })} />
            <FieldInput label="Source" placeholder="api, browser, send2, service logger…" value={draft.provider} onChange={(e) => setDraft({ ...draft, provider: e.target.value })} />
            <FieldSelect label="Severity" value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })}><option value="">All severities</option><option value="error">Error</option><option value="warning">Warning</option></FieldSelect>
            <FieldInput label="HTTP status" type="number" min={0} max={599} placeholder="e.g. 500 or 422" value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })} />
            {!scopedTenant && <FieldInput label="Tenant ID" placeholder="All tenants" value={draft.tenant} onChange={(e) => setDraft({ ...draft, tenant: e.target.value })} />}
            <FieldInput label="From date" type="date" value={draft.since} max={draft.until || undefined} onChange={(e) => setDraft({ ...draft, since: e.target.value })} />
            <FieldInput label="To date" type="date" value={draft.until} min={draft.since || undefined} onChange={(e) => setDraft({ ...draft, until: e.target.value })} />
            <div className="flex flex-wrap items-end gap-2"><PrimaryButton type="submit"><Search className="h-4 w-4" />Apply filters</PrimaryButton><GhostButton onClick={() => { setDraft(emptyFilters); setFilters(emptyFilters); setOffset(0) }}>Clear</GhostButton></div>
          </div>
        </form>
      </Card>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-txmuted">
        <span>{total} matching events{updatedAt ? ` · Updated ${formatDate(updatedAt)}` : ''}</span>
        <label className="flex items-center gap-2"><input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />Auto-refresh every 15 seconds</label>
      </div>
      {state.error && <ErrorBanner title="Could not load errors" message={state.error} />}
      {state.loading && !state.data && <LoadingBlock label="Loading errors…" />}
      {!state.loading && !state.error && rows.length === 0 && (
        <Card>
          <EmptyState
            title="No errors recorded"
            description="No recorded events match these filters. An empty log alone does not confirm every service is healthy."
          />
        </Card>
      )}
      <div className="space-y-3">
        {rows.map((row) => (
          <Card key={row.id} className="p-4 sm:p-5">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-sm text-tx">
                <span className="font-medium">{row.api || 'Unknown API'}</span>
                {row.provider && <Pill>{row.provider}</Pill>}
                {row.http_status != null ? <Pill tone={row.http_status >= 500 ? 'bad' : 'warn'}>HTTP {row.http_status}</Pill> : null}
                {row.severity && <Pill>{row.severity}</Pill>}
                <span className="text-xs text-txfaint">{formatDate(row.created_at)}</span>
              </div>
              {row.message && <p className="text-sm text-tx">{row.message}</p>}
              <div className="flex flex-wrap items-center gap-3 text-xs text-txmuted">
                <span>Tenant: {row.tenant_id || 'Platform'}</span>
                {row.request_id && <RequestId value={row.request_id} />}
              </div>
              {row.detail && <details><summary className="cursor-pointer text-xs font-medium text-acc">Trace details</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-anywhere scroll-thin rounded-lg border border-line bg-paper p-3 font-mono text-xs leading-relaxed text-txmuted">{row.detail}</pre></details>}
            </div>
          </Card>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-txmuted"><span>{total ? `${offset + 1}–${offset + rows.length} of ${total}` : '0 events'}</span><div className="flex gap-2"><GhostButton disabled={!offset || state.loading} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</GhostButton><GhostButton disabled={state.loading || !(state.data?.has_more ?? offset + rows.length < total)} onClick={() => setOffset(offset + pageSize)}>Next</GhostButton></div></div>
    </div>
  )
}
