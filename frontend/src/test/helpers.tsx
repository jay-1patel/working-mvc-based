import { render, waitFor, screen } from '@testing-library/react'
import { setCredentials, setToken } from '@/lib/api'
import App from '@/App'

export function renderWithShell() {
  setToken(null)
  return render(<App />)
}

export function renderApp(hash = '#/tenants') {
  window.location.hash = hash
  // Username + session_id auth — a bare opaque token no longer authenticates.
  setCredentials('root', 'test-session')
  const utils = render(<App />)
  return utils
}

export async function waitForScreen() {
  await waitFor(() => {
    const stillLoading =
      screen.queryByText(/Connecting to the backend|Loading tenants/) !== null
    if (stillLoading) throw new Error('still loading')
  }, { timeout: 3000 })
}

export async function openView(hash: string) {
  window.location.hash = hash
  window.dispatchEvent(new HashChangeEvent('hashchange'))
  await waitForScreen()
}
