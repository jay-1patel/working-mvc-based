import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp } from '../helpers'
import { testState } from '../fixture-server'

describe('searchable error trace log', () => {
  it('searches by request ID and expands stack details', async () => {
    testState.respond('GET /api/admin/errors', ({ url }) => ({ body: {
      count: 1, total: 1, has_more: false,
      errors: [{ id: 1, api: 'POST /api/tenants/acme/upload', provider: 'api',
        message: url.searchParams.get('search') ? 'Matching request' : 'Upload failed',
        tenant_id: 'acme', request_id: 'req_trace_123', http_status: 500,
        detail: 'ValueError: document indexing failed' }],
    } }))
    renderApp('#/errors')
    expect(await screen.findByText('Upload failed')).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Search logs'), 'req_trace_123')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))
    expect(await screen.findByText('Matching request')).toBeInTheDocument()
    expect(testState.calls.some((call) => call.path.includes('search=req_trace_123'))).toBe(true)
    await user.click(screen.getByText('Trace details'))
    expect(screen.getByText('ValueError: document indexing failed')).toBeVisible()
    expect(screen.getByRole('checkbox', { name: 'Auto-refresh every 15 seconds' })).toBeChecked()
  })

  it('loads older records instead of stopping at the latest page', async () => {
    testState.respond('GET /api/admin/errors', ({ url }) => ({ body: {
      count: 1, total: 51, has_more: url.searchParams.get('offset') === '0',
      errors: [{ id: 1, message: url.searchParams.get('offset') === '50' ? 'Older failure' : 'Latest failure' }],
    } }))
    renderApp('#/errors')
    await screen.findByText('Latest failure')
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Older failure')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Previous' }))
    await waitFor(() => expect(screen.getByText('Latest failure')).toBeInTheDocument())
  })
})
