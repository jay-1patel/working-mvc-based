import { afterEach, describe, expect, it, vi } from 'vitest'
import { captureClientError, flushClientErrors } from '@/lib/client-errors'
import { setToken } from '@/lib/api'

afterEach(() => { vi.restoreAllMocks(); setToken(null) })
const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('browser diagnostic delivery', () => {
  it('retries a failed delivery without sending credentials in the diagnostic body', async () => {
    setToken('session-a')
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('Offline'))
      .mockResolvedValue({ ok: true, status: 202 } as Response)
    const id = captureClientError('Cannot reach backend', '', 'GET /api/orders?token=private')
    await tick()
    await flushClientErrors()
    expect(fetch).toHaveBeenCalledTimes(2)
    const body = JSON.parse(String(fetch.mock.calls[1][1]?.body))
    expect(body.request_id).toBe(id)
    expect(body.api).toBe('GET /api/orders')
    expect(JSON.stringify(body)).not.toContain('session-a')
    expect(JSON.stringify(body)).not.toContain('private')
  })

  it('does not upload an earlier session’s errors under a new account', async () => {
    setToken('previous-session')
    const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Offline'))
    captureClientError('Previous account error')
    await tick()
    setToken('new-session')
    await flushClientErrors()
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
