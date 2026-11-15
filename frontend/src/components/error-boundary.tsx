import { Component, type ErrorInfo, type ReactNode } from 'react'
import { captureClientError } from '@/lib/client-errors'

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean; requestId: string }> {
  state = { failed: false, requestId: '' }

  static getDerivedStateFromError() { return { failed: true } }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const requestId = captureClientError(error.message, `${error.stack || ''}\n${info.componentStack || ''}`, 'React render')
    this.setState({ requestId })
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="send2-frame">
        <div className="send2-workspace flex min-h-0 flex-1 items-center justify-center bg-paper p-6">
          <section role="alert" className="send2-panel max-w-md rounded-panel bg-card p-6">
            <img src="/send2digital-logo.png" alt="Send2Digital" className="mb-6 w-40" />
            <h1 className="text-xl font-semibold text-heading">This screen ran into a problem</h1>
            <p className="mt-3 text-sm text-txmuted">Reload the page to try again. Share this reference with your administrator.</p>
            <p className="my-4 break-all font-mono text-xs text-tx">{this.state.requestId}</p>
            <button className="rounded-lg bg-acc px-4 py-2 text-sm text-onacc" onClick={() => window.location.reload()}>Reload page</button>
          </section>
        </div>
      </div>
    )
  }
}
