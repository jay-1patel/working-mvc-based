import { useState } from 'react'
import { KeyRound, Loader2, LogIn, UserPlus } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { ApiError } from '@/lib/api'
import { FieldInput, Notice, PrimaryButton } from '@/components/remake/ui'
import { PASSWORD_HINT, passwordError } from '@/lib/password'

export function LoginView() {
  const { needsSetup, login, setup } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (needsSetup) {
      const problem = passwordError(password)
      if (problem) {
        setError(problem)
        return
      }
    }
    setBusy(true)
    setError(null)
    try {
      if (needsSetup) await setup(username, password, email)
      else await login(username, sessionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="send2-frame">
    <div className="send2-workspace flex min-h-0 flex-1 items-center justify-center overflow-y-auto bg-paper px-5 py-8 text-tx sm:py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <img src="/send2digital-logo.png" alt="Send2Digital" className="mx-auto mb-6 h-auto w-48" />
          <h1 className="text-xl font-semibold text-heading">AI Chatbot</h1>
          <p className="mt-1.5 text-xs leading-relaxed text-txmuted">
            {needsSetup
              ? 'No admin exists yet. Create the first super admin to start registering tenants.'
              : 'Sign in to your business workspace.'}
          </p>
        </div>

        <form onSubmit={submit} className="send2-panel space-y-4 rounded-panel border border-line bg-card p-6 sm:p-8">
          <FieldInput
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
            hint={needsSetup ? undefined : 'Plain username, e.g. test_support_ (backend encodes it).'}
          />
          {needsSetup ? (
            <FieldInput
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              hint={PASSWORD_HINT}
              required
            />
          ) : (
            <FieldInput
              label="Session ID"
              type="password"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              autoComplete="current-password"
              hint="Use the live session_id for this admin from the database."
              required
            />
          )}
          {needsSetup && (
            <FieldInput
              label="Email (optional)"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          )}

          {error && <Notice tone="bad">{error}</Notice>}

          <PrimaryButton type="submit" className="w-full" disabled={busy}>
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : needsSetup ? (
              <UserPlus className="h-4 w-4" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {needsSetup ? 'Create super admin' : 'Sign in'}
          </PrimaryButton>
        </form>

        <p className="mt-6 flex items-center justify-center gap-2 text-xs text-txfaint">
          <KeyRound className="h-3 w-3" />
          Sessions are stored locally in this browser only.
        </p>
      </div>
    </div>
    <footer className="send2-footer">Send2Digital <span aria-hidden="true">·</span> AI Chatbot</footer>
    </div>
  )
}
