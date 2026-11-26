import type { AdminIdentity, Agent, ChatTurn, InboxItem, ResolvedProfile, Tenant } from './types'

export const MOCK_MODE_KEY = 'tenant-console.mock_mode'

/** Mock mode is intentionally limited to local Vite development. */
export function isMockMode(): boolean {
  if (!import.meta.env.DEV || typeof window === 'undefined' || typeof localStorage === 'undefined') return false
  return (
    localStorage.getItem(MOCK_MODE_KEY) === '1' ||
    window.location.search.includes('mock=1') ||
    window.location.hash.includes('mock=1')
  )
}

export function enableMockMode() {
  localStorage.setItem(MOCK_MODE_KEY, '1')
}

export function disableMockMode() {
  localStorage.removeItem(MOCK_MODE_KEY)
}

export const mockIdentity: AdminIdentity = {
  id: 0,
  username: 'simple_admin',
  role: 'admin',
  tenant_id: '15',
  onboarding_approved: true,
  email: 'mock@example.test',
  permissions: {
    manage_operations: true,
    view_inbox: true,
    view_customers: true,
    upload_faq: true,
    upload_kb: true,
    view_files: true,
  },
  menu_privileges: {
    graphic: true,
    chats: true,
    profile: true,
    customer: true,
    website_crawler: true,
    setup_chatbot: true,
    menu: true,
  },
}

export const mockTenant: Tenant = {
  id: '15',
  slug: 'demo-retail',
  vertical: 'ecommerce',
  display_name: 'Demo Retail',
  waba_phone_id: 'mock-wa',
  status: 'active',
  current_version: 1,
  created_at: '2026-01-01T00:00:00Z',
}

export const mockInbox: InboxItem[] = [
  {
    wa_id: '919876543210',
    name: 'Priya Sharma',
    last_message: 'Can you help me with my order?',
    last_message_at: '2026-11-22T10:20:00Z',
    turns: 4,
    bot_state: null,
    handover_mode: 'human',
    assigned_agent_id: null,
    resolved: false,
  },
  {
    wa_id: '919812345678',
    name: 'Arjun Mehta',
    last_message: 'I would like to see the new arrivals.',
    last_message_at: '2026-11-22T10:28:00Z',
    turns: 2,
    bot_state: null,
    handover_mode: 'bot',
    assigned_agent_id: 'mock_admin',
    resolved: true,
  },
]

export const mockAgents: Agent[] = [
  { agent_id: 'mock_admin', username: 'Mock admin', status: 'online' },
]

export const mockTurns: ChatTurn[] = [
  {
    id: 1,
    wa_id: '919876543210',
    sender_name: 'Priya Sharma',
    message: 'Can you help me with my order?',
    response: 'I can help with that. Let me check the order details.',
    route: 'orders',
    created_at: '2026-11-22T10:18:00Z',
    user_message: 'Can you help me with my order?',
  },
  {
    id: 2,
    wa_id: '919876543210',
    sender_name: 'Priya Sharma',
    message: 'The tracking link is not working.',
    response: '',
    route: 'handoff',
    created_at: '2026-11-22T10:20:00Z',
    user_message: 'The tracking link is not working.',
  },
]

export const mockProfile: ResolvedProfile = {
  tenant_id: mockTenant.id,
  vertical: 'ecommerce',
  version: 1,
  source: 'mock',
  features: {
    cart: true, buy_now: true, orders: true, track_order: true, returns: true,
    brochure_pdf: true, distributors: true, offerings: true, offering_details: true,
    services: false, products: true, products_schemes: false, payments: false,
    lead_capture: true, quote: true, callback: true, book_appointment: true,
    handoff: true, faq: true, kb: true, complaints: true, campaigns: true,
    human_handover: true, message_intelligence: false, topic_tagging: false,
    safety_escalation: false, repeat_issue_detection: false,
  },
  vocabulary: {},
  brand: {
    name: 'Demo Retail', tagline: 'Mock workspace', website: '',
    support_email: 'support@example.test', support_phone: '', signature: '— Demo Retail', bot_name: 'Demo Bot',
  },
  business_hours: { timezone: 'Asia/Kolkata', always_open: true, open: '00:00', close: '23:59', open_days: [0, 1, 2, 3, 4, 5, 6], out_of_hours_message: '' },
  guardrails: { never_state: [], never_state_notes: {}, escalate_keywords: [], escalation_message: '', forbidden_terms: [], handoff_keywords: [] },
  notifications: { sales_email: '', support_email: '', brochure_url: '', brochure_label: '', channels: [] },
  menu: { key: 'main', header: '', body: '', footer: '', button_text: '', buttons: [] },
  active_intents: [], inactive_intents: [], flows: [],
}
