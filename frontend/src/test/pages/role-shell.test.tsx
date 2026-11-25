import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ALL_PERMISSIONS } from '@/lib/permissions'
import { renderApp, waitForScreen } from '../helpers'
import { testState } from '../fixture-server'

describe('Send2Digital role workspaces', () => {
  it.each(['super_admin', 'admin', 'sub_admin'] as const)(
    'keeps the AI Chatbot brand and correct navigation for %s',
    async (role) => {
      testState.respond('GET /api/auth/me', () => ({
        body: {
          id: 2,
          username: 'workspace-user',
          role,
          tenant_id: role === 'super_admin' ? null : 'acme',
          onboarding_approved: true,
          permissions: role === 'sub_admin'
            ? { view_customers: true, view_inbox: true }
            : Object.fromEntries(ALL_PERMISSIONS.map((permission) => [permission, true])),
        },
      }))
      renderApp('#/tenants/acme/customers')
      await waitForScreen()
      expect(await screen.findByRole('heading', { name: 'Customers' })).toBeInTheDocument()
      expect(screen.getAllByAltText('Send2Digital').length).toBeGreaterThan(0)
      expect(screen.getAllByText('AI Chatbot').length).toBeGreaterThan(0)
      const navigation = within(screen.getByRole('navigation', { name: 'Main navigation' }))
      expect(navigation.getByRole('button', { name: 'Customers' })).toBeInTheDocument()
      if (role === 'super_admin') {
        // Inside a tenant: same sidebar as admin + Manage (People / Activity / Errors).
        expect(screen.getByText(/View-only — use Onboarded users/)).toBeInTheDocument()
        expect(navigation.getByText('Manage')).toBeInTheDocument()
        expect(navigation.getByRole('button', { name: 'People / privileges' })).toBeInTheDocument()
        expect(navigation.getByRole('button', { name: 'Business requests' })).toBeInTheDocument()
        expect(navigation.getByRole('button', { name: 'Activity log' })).toBeInTheDocument()
        expect(navigation.getByRole('button', { name: 'Errors & health' })).toBeInTheDocument()
        // Platform links stay off the tenant sidebar.
        expect(navigation.queryByRole('button', { name: 'Businesses' })).not.toBeInTheDocument()
      } else {
        expect(navigation.queryByRole('button', { name: 'Businesses' })).not.toBeInTheDocument()
        expect(screen.queryByText(/View-only — use Onboarded users/)).not.toBeInTheDocument()
        expect(navigation.queryByRole('button', { name: 'People / privileges' })).not.toBeInTheDocument()
      }
      // Grow / Versions / Connections / Past chats / etc. are not in the admin sidebar.
      expect(navigation.queryByText('Grow')).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Questions the bot understands' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Versions' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Connections' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Past chats' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Help requests' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Callbacks' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: /& prices/ })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Layers' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'Test & smoke' })).not.toBeInTheDocument()
      expect(navigation.queryByRole('button', { name: 'WhatsApp Tester' })).not.toBeInTheDocument()
      if (role === 'sub_admin') {
        expect(screen.queryByRole('button', { name: 'Register a tenant' })).not.toBeInTheDocument()
        expect(navigation.queryByRole('button', { name: 'People' })).not.toBeInTheDocument()
      }
      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: 'Open navigation' }))
      await user.keyboard('{Escape}')
      expect(screen.getAllByRole('button', { name: 'Close navigation', exact: true })).toHaveLength(1)
    },
  )
})
