import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BotMenuPanel } from '@/components/tenants/bot-menu-panel'

const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }))

vi.mock('@/lib/router', () => ({ navigate }))
vi.mock('@/lib/permissions', () => ({
  usePermissions: () => ({
    canWriteTenant: (permission: string) => permission === 'manage_operations',
    isSuperAdmin: false,
  }),
}))
vi.mock('@/components/tenants/hooks', () => ({
  useResolved: () => ({
    loading: false,
    error: null,
    data: {
      version: 3,
      menu: {
        body: 'How can we help?',
        buttons: [
          {
            id: 'menu_help',
            title: 'Help',
            description: 'Get help',
            sort_order: 0,
            enabled: true,
          },
        ],
      },
    },
  }),
  useTenantDetail: () => ({
    data: {
      has_draft: false,
      layers: { db: null, file: null, resolved: null },
    },
  }),
}))

describe('BotMenuPanel', () => {
  beforeEach(() => navigate.mockClear())

  it('offers an edit action for each menu option and opens that option', () => {
    render(<BotMenuPanel tenantId="acme" />)

    fireEvent.click(screen.getByRole('button', { name: 'Edit Help' }))

    expect(navigate).toHaveBeenCalledWith('/tenants/acme/menu-edit?focus=menu_help')
  })
})
