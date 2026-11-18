/**
 * A tiny in-test HTTP layer: replaces global fetch with a routing table so
 * every screen can be exercised against realistic API payloads without a
 * backend. Tests can override any route's response via `testState.respond`.
 */
import { vi } from 'vitest'
import { fixtures } from './fixtures'

type Handler = (ctx: {
  url: URL
  method: string
  body: any
}) => { status?: number; body: unknown } | Promise<{ status?: number; body: unknown }>

interface State {
  calls: { method: string; path: string; body?: unknown }[]
  respond: (methodAndPath: string, handler: Handler) => void
  reset: () => void
}

const overrides = new Map<string, Handler>()

const json = (body: unknown, status = 200) => ({ status, body })

export const testState: State = {
  calls: [],
  respond(methodAndPath, handler) {
    overrides.set(methodAndPath, handler)
  },
  reset() {
    testState.calls.length = 0
    overrides.clear()
  },
}

function resolve(method: string, path: string, body: unknown) {
  const url = new URL(path, 'http://localhost')
  const pathOnly = url.pathname
  const overrideKey = [...overrides.keys()].find((k) => {
    const [m, p] = k.split(' ')
    if (m !== method) return false
    if (p.endsWith('*')) return pathOnly.startsWith(p.substring(0, p.length - 1))
    return p === pathOnly
  })
  const handler = overrideKey ? overrides.get(overrideKey) : undefined
  if (handler) return handler({ url, method, body })
  return routeDefault(method, pathOnly, url, body)
}

function routeDefault(
  method: string,
  path: string,
  _url: URL,
  body: any,
): { status?: number; body: unknown } {
  // ── auth ──────────────────────────────────────────────────────────────
  if (path === '/api/auth/status') return json({ has_admins: true })
  if (path === '/api/auth/login' && method === 'POST') return json({ token: 'test-token' })
  if (path === '/api/auth/me')
    return json(fixtures.identity)
  if (path === '/api/auth/first-admin' && method === 'POST')
    return json({ token: 'test-token' })
  if (path === '/api/auth/create' && method === 'POST')
    return json({ status: 'created', username: body?.username, role: body?.role ?? 'sub_admin', permissions: body?.permissions ?? {} })
  if (path === '/api/auth/admins') return json({ admins: fixtures.admins })
  const adminMatch = path.match(/^\/api\/auth\/admins\/([^/]+)$/)
  if (adminMatch) {
    const username = decodeURIComponent(adminMatch[1])
    if (method === 'DELETE')
      return json({ status: `removed ${username}` })
    if (method === 'PATCH')
      return json({ status: 'updated', username, role: body?.role ?? 'sub_admin', permissions: body?.permissions ?? {} })
  }
  if (path.match(/^\/api\/auth\/admins\/[^/]+\/reset-password$/) && method === 'POST')
    return json({ status: 'password reset' })

  // ── dashboard / analytics (overview home) ───────────────────────────
  if (path === '/api/admin/dashboard/overview')
    return json({
      days: 7,
      kb_files: 2,
      faq_files: 1,
      products: 4,
      top_questions: [{ query: 'hours?', count: 3 }],
      total_customers: 12,
      total_orders: 5,
      orders_solved: 3,
      total_complaints: 2,
      complaints_solved: 1,
      total_messages: 40,
      unique_users: 8,
      avg_response_ms: 120,
      route_breakdown: [
        { route: 'faq', count: 20 },
        { route: 'kb', count: 12 },
        { route: 'agent', count: 8 },
      ],
      response_time: [
        { date: '2026-11-09', avg_ms: 110, count: 4 },
        { date: '2026-11-10', avg_ms: 130, count: 6 },
        { date: '2026-11-11', avg_ms: 100, count: 5 },
      ],
      total_unique_questions: 1,
      frequent_questions: [{ query: 'hours?', count: 3, last_asked: '2026-11-11T10:00:00Z' }],
    })
  if (path === '/api/admin/onboarding-kits/list' && method === 'POST')
    return json({ templates: [] })

  // ── tenants ─────────────────────────────────────────────────────────
  if (path === '/api/admin/tenants' && method === 'GET') return json({ tenants: fixtures.tenants })
  if (path === '/api/admin/tenants' && method === 'POST')
    return json({ ok: true, tenant: { ...fixtures.tenant, ...body } })
  if (method === 'POST') {
    if (path === '/api/admin/tenants/resolved') return json(fixtures.resolved)
    if (path === '/api/admin/tenants/conversations/detail') return json({ wa_id: body?.wa_id, messages: fixtures.turns })
    if (path === '/api/admin/tenants/chat-history') return json({ history: fixtures.turns })
    if (path === '/api/admin/tenants/inbox') return json({ queue: fixtures.inbox, count: fixtures.inbox.length, handoff_count: 1 })
    if (path === '/api/admin/tenants/agents') return json({ agents: fixtures.agents })
    if (path === '/api/admin/tenants/inbox/reply') return json({ status: 'sent' })
    if (path === '/api/admin/tenants/inbox/assign') return json({ status: 'assigned' })
    if (path === '/api/admin/tenants/inbox/handover') return json({ status: 'updated' })
    if (path === '/api/admin/tenants/inbox/resolve') return json({ status: 'resolved' })
    if (path === '/api/admin/tenants/complaints') return json({ complaints: fixtures.complaints, count: fixtures.complaints.length, open_count: 1 })
    if (path === '/api/admin/tenants/complaints/update') return json({ status: 'updated' })
    if (path === '/api/admin/tenants/complaints/reply') return json({ status: 'sent' })
    if (path === '/api/admin/tenants/complaints/delete') return json({ status: 'deleted' })
    if (path === '/api/admin/tenants/customers') return json({ customers: fixtures.customers, count: fixtures.customers.length })
    if (path === '/api/admin/tenants/files') return json({ files: fixtures.files })
    if (path === '/api/admin/tenants/files/upload') return json({ status: 'uploaded', filename: body?.filename, chunks: 3, size: 1234, file_url: '/f' })
    if (path === '/api/admin/tenants/files/delete') return json({ status: 'deleted' })
    if (path === '/api/admin/tenants/knowledge-gaps') return json({ gaps: [], summary: { total_unresolved: 0, top_queries: [] } })
    if (path === '/api/admin/tenants/knowledge-gaps/resolve') return json({ status: 'ok', gap_id: body?.gap_id, resolved: true })
  }
  const m = path.match(/^\/api\/admin\/tenants\/([^/]+)(\/.*)?$/)
  if (m) {
    const id = decodeURIComponent(m[1])
    const sub = m[2] ?? ''
    if (sub === '' && method === 'DELETE') return json({ ok: true })
    if (sub === '' && method === 'GET')
      return json({ count: fixtures.offerings.length, columns: fixtures.recordSchema.columns, offerings: fixtures.offerings })
    if (sub === '/phone-id' && method === 'POST') return json({ ok: true })
    if (sub === '/detail') return json(fixtures.layerDetail)
    if (sub === '/resolved') return json(fixtures.resolved)
    if (sub === '/profile' && method === 'POST') return json({ ok: true, validation: [] })
    if (sub === '/publish') return json({ ok: true, version: 3, active_intents: ['greeting'], visible_buttons: ['menu_help'] })
    if (sub === '/versions' && method === 'GET') return json(fixtures.versions)
    if (sub === '/versions' && method === 'POST') return json({ ok: true, version: 3, active: 3 })
    const vm = sub.match(/^\/versions\/(\d+)$/)
    if (vm) return json(fixtures.versionSnapshot)
    if (sub === '/rollback' && method === 'POST') return json({ ok: true, version: body?.version ?? 2, active: body?.version ?? 2 })
    if (sub === '/tokens' && method === 'GET') return json({ tenant_id: id, tokens: fixtures.tokens })
    if (sub === '/tokens' && method === 'POST')
      return json({ ok: true, id: 99, token: 'tk_new_token', warning: 'Copy it now' })
    const tm = sub.match(/^\/tokens\/(\d+)$/)
    if (tm && method === 'DELETE') return json({ ok: true })
    if (sub === '/test-question' && method === 'POST')
      return json({ tenant_id: id, message: body?.message ?? '', intent: 'greeting', score: 0.9, tier: 'high', flow: null, active_intents: ['greeting'] })
    if (sub === '/smoke') return json(fixtures.smoke)
    if (sub === '/customers' && method === 'GET') return json({ customers: fixtures.customers, count: fixtures.customers.length })
    if (sub === '/callbacks' && method === 'GET')
      return json({ ok: true, callbacks: fixtures.callbacks, total_count: fixtures.callbacks.length })
    const cbMatch = sub.match(/^\/callbacks\/([^/]+)\/(cancel|complete|schedule)$/)
    if (cbMatch && method === 'POST')
      return json({ ok: true, message: 'done', meet_link: cbMatch[2] === 'schedule' ? 'https://meet.google.com/test' : null })
    if (sub === '/orders' && method === 'GET') return json({ orders: fixtures.orders, count: fixtures.orders.length, counts: fixtures.orderCounts })
    if (sub === '/offerings' && method === 'GET') return json({ offerings: fixtures.offerings, columns: fixtures.recordSchema.columns, count: fixtures.offerings.length })
    if (sub === '/offerings' && method === 'POST') return json({ ok: true, id: 42 })
    const om = sub.match(/^\/offerings\/(\d+)$/)
    if (om && method === 'PUT') return json({ ok: true })
    if (om && method === 'DELETE') return json({ ok: true })
    if (sub === '/offerings/reorder' && method === 'POST') return json({ ok: true })
    if (sub === '/record-schema' && method === 'GET') return json(fixtures.recordSchema)
    if (sub === '/record-schema/columns' && method === 'POST') return json({ ok: true, id: 10 })
    const cm = sub.match(/^\/record-schema\/columns\/([^/]+)$/)
    if (cm) {
      if (method === 'PUT') return json({ ok: true })
      if (method === 'DELETE') return json({ ok: true })
    }
    if (sub === '/record-schema/reset' && method === 'POST') return json({ ok: true })
    const rcm = sub.match(/^\/records(\/(\d+))?$/)
    if (rcm) {
      if (method === 'GET') return json({ records: fixtures.records, count: fixtures.records.length })
      if (method === 'POST') return json({ ok: true, id: 50 })
      if (method === 'PUT') return json({ ok: true })
      if (method === 'DELETE') return json({ ok: true })
    }
    if (sub === '/conversations' && method === 'GET')
      return json({ conversations: fixtures.threads, count: fixtures.threads.length })
    const convMatch = sub.match(/^\/conversations\/([^/]+)$/)
    if (convMatch && method === 'GET') return json({ turns: fixtures.turns })
    if (sub === '/chat-history' && method === 'GET')
      return json({ history: fixtures.turns })
    if (sub === '/inbox' && method === 'GET') return json({ queue: fixtures.inbox })
    if (sub === '/agents' && method === 'GET') return json({ agents: fixtures.agents })
    const inboxReply = sub.match(/^\/inbox\/([^/]+)\/reply$/)
    if (inboxReply && method === 'POST') return json({ status: 'sent' })
    if (sub === '/inbox/assign' && method === 'POST') return json({ status: 'assigned' })
    const handover = sub.match(/^\/inbox\/handover\/(.+)$/)
    if (handover && method === 'POST') return json({ status: 'updated' })
    const resolveInbox = sub.match(/^\/inbox\/resolve\/(.+)$/)
    if (resolveInbox && (method === 'POST' || method === 'DELETE')) return json({ status: 'resolved' })
    if (sub === '/complaints' && method === 'GET') return json({ complaints: fixtures.complaints })
    const complaintMatch = sub.match(/^\/complaints\/([^/]+)$/)
    if (complaintMatch) {
      if (method === 'PUT') return json({ status: 'updated' })
      if (method === 'DELETE') return json({ status: 'deleted' })
    }
    const complaintReply = sub.match(/^\/complaints\/([^/]+)\/reply$/)
    if (complaintReply && method === 'POST') return json({ status: 'sent' })
    if (sub === '/campaigns' && method === 'GET') return json({ campaigns: fixtures.campaigns, stats: fixtures.campaignStats })
    if (sub === '/campaigns' && method === 'POST') return json({ ok: true, id: 7 })
    const campMatch = sub.match(/^\/campaigns\/(\d+)$/)
    if (campMatch) {
      if (method === 'PUT') return json({ ok: true })
      if (method === 'DELETE') return json({ ok: true })
    }
    if (sub === '/distributors' && method === 'GET') return json({ distributors: fixtures.distributors })
    if (sub === '/distributors' && method === 'POST') return json({ ok: true, wa_id: body?.wa_id })
    const distMatch = sub.match(/^\/distributors\/([^/]+)$/)
    if (distMatch) {
      if (method === 'PUT') return json({ ok: true })
      if (method === 'DELETE') return json({ ok: true })
    }
    if (sub === '/files' && method === 'GET') return json({ files: fixtures.files })
    if (sub === '/files/upload' && method === 'POST') return json({ status: 'uploaded', filename: 'a.pdf', chunks: 3, size: 1234, file_url: '/f' })
    const fileMatch = sub.match(/^\/files\/([^/]+)(\/(preview|download))?$/)
    if (fileMatch) {
      if (method === 'DELETE') return json({ status: 'deleted' })
      return json({ url: 'http://localhost/blob' })
    }
    if (sub === '/chat/users' && method === 'GET') return json({ users: fixtures.chatUsers })
    if (sub === '/chat/send' && method === 'POST') return json({ status: 'sent', reply: 'Hello!' })
  }

  // ── shared platform tables ────────────────────────────────────────────
  if (path === '/api/admin/customers') return json({ customers: fixtures.customers, count: fixtures.customers.length })
  if (path === '/api/orders') return json({ orders: fixtures.orders, count: fixtures.orders.length, counts: fixtures.orderCounts })

  return json({ detail: `No test fixture for ${method} ${path}` }, 404)
}

export const fixtureServer = {
  originalFetch: globalThis.fetch,
  install() {
    globalThis.fetch = vi.fn(async (input: any, init?: RequestInit) => {
      const path = typeof input === 'string' ? input : input.url
      const method = (init?.method ?? 'GET').toUpperCase()
      let body: unknown
      if (init?.body) {
        try {
          body = JSON.parse(String(init.body))
        } catch {
          body = init.body
        }
      }
      testState.calls.push({ method, path, body })
      const result = await resolve(method, path, body)
      const status = result.status ?? 200
      return {
        ok: status >= 200 && status < 300,
        status,
        statusText: status === 200 ? 'OK' : 'Error',
        json: async () => result.body,
        text: async () => JSON.stringify(result.body),
        blob: async () =>
          new Blob([
            typeof result.body === 'string'
              ? result.body
              : JSON.stringify(result.body),
          ]),
      } as Response
    }) as unknown as typeof fetch
  },
  restore() {
    globalThis.fetch = fixtureServer.originalFetch
  },
}

