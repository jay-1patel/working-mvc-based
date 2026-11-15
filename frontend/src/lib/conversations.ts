/**
 * Tenant conversations — chat history, the live inbox and complaints.
 *
 * Every route is tenant-scoped: the tenant is a path segment and the server
 * refuses a token that belongs to another one. These read the same
 * `chat_history` the bot writes, filtered to this tenant.
 */

import { api } from './api'
import type { Attachment } from './attachments'
import type { Agent, ChatTurn, Complaint, ConversationThread, InboxItem } from './types'

const base = (tenantId: string) => `/api/admin/tenants/${encodeURIComponent(tenantId)}`

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const tail = search.toString()
  return tail ? `?${tail}` : ''
}

/** `[faq] hello` -> `hello`; a row with no prefix is returned unchanged. */
export function stripRoute(message: string): string {
  return message.startsWith('[') && message.includes('] ')
    ? message.slice(message.indexOf('] ') + 2)
    : message
}

export const conversationsApi = {
  threads: (
    tenantId: string,
    opts: { search?: string; limit?: number } = {},
    signal?: AbortSignal,
  ) =>
    api
      .get<{ conversations: ConversationThread[]; count: number }>(
        `${base(tenantId)}/conversations${query(opts)}`,
        signal,
      )
      .then((r) => r.conversations),

  thread: (tenantId: string, waId: string, limit = 300, signal?: AbortSignal) =>
    api.post<{ wa_id: string; messages: ChatTurn[] }>(
      '/api/admin/tenants/conversations/detail',
      { tenant_id: tenantId, wa_id: waId, limit },
      { signal },
    ),

  history: (
    tenantId: string,
    opts: { days?: number; search?: string; waId?: string; limit?: number } = {},
    signal?: AbortSignal,
  ) =>
    api
      .post<{ history: ChatTurn[] }>('/api/admin/tenants/chat-history', {
        tenant_id: tenantId,
        days: opts.days,
        search: opts.search,
        wa_id: opts.waId,
        limit: opts.limit,
      }, { signal })
      .then((r) => r.history),

  inbox: (tenantId: string, includeResolved = false, signal?: AbortSignal) =>
    api.post<{ queue: InboxItem[]; count: number; handoff_count: number }>(
      '/api/admin/tenants/inbox',
      { tenant_id: tenantId, include_resolved: includeResolved },
      { signal },
    ),

  setHandover: (tenantId: string, waId: string, mode: 'bot' | 'human') =>
    api.post<{ status: string }>('/api/admin/tenants/inbox/handover', { tenant_id: tenantId, wa_id: waId, mode }),

  assign: (tenantId: string, waId: string, agentId: string) =>
    api.post<{ status: string }>('/api/admin/tenants/inbox/assign', { tenant_id: tenantId, wa_id: waId, agent_id: agentId }),

  resolve: (tenantId: string, waId: string, reply = true) =>
    api.post<{ status: string; notified: boolean }>(
      '/api/admin/tenants/inbox/resolve',
      { tenant_id: tenantId, wa_id: waId, reply },
    ),

  reply: (tenantId: string, waId: string, message: string, attachment?: Attachment | null) =>
    api.post<{ status: string; sent: boolean }>(
      '/api/admin/tenants/inbox/reply',
      { tenant_id: tenantId, wa_id: waId, message, attachment: attachment ?? undefined },
    ),

  agents: (tenantId: string, signal?: AbortSignal) =>
    api.post<{ agents: Agent[] }>('/api/admin/tenants/agents', { tenant_id: tenantId }, { signal }).then((r) => r.agents),

  complaints: (
    tenantId: string,
    opts: { status?: string; limit?: number } = {},
    signal?: AbortSignal,
  ) =>
    api.post<{ complaints: Complaint[]; count: number; open_count: number }>(
      '/api/admin/tenants/complaints',
      { tenant_id: tenantId, status: opts.status, limit: opts.limit },
      { signal },
    ),

  updateComplaint: (
    tenantId: string,
    ticketId: string,
    body: { status?: string; priority?: string; assigned_to?: string },
  ) => api.post<{ status: string }>('/api/admin/tenants/complaints/update', {
    tenant_id: tenantId,
    ticket_id: ticketId,
    ...body,
  }),

  replyComplaint: (tenantId: string, ticketId: string, message: string, status?: string) =>
    api.post<{ status: string; sent: boolean; new_status: string | null }>(
      '/api/admin/tenants/complaints/reply',
      { tenant_id: tenantId, ticket_id: ticketId, message, status },
    ),

  deleteComplaint: (tenantId: string, ticketId: string) =>
    api.post<{ status: string }>('/api/admin/tenants/complaints/delete', {
      tenant_id: tenantId,
      ticket_id: ticketId,
    }),
}

export const COMPLAINT_STATUSES = ['open', 'in_progress', 'awaiting_info', 'resolved', 'closed']
export const COMPLAINT_PRIORITIES = ['low', 'normal', 'high', 'urgent']
