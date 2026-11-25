import { useEffect, useMemo, useState } from 'react'
import { Loader2, Pencil, Save, Send, TriangleAlert } from 'lucide-react'
import { useAction, useAsync } from '@/lib/hooks'
import { tenantsApi } from '@/lib/tenants'
import {
  editorContactErrors,
  editorFromProfile,
  editorToSnapshot,
  isValidPhone,
  timezoneOptions,
  type EditorForm,
} from '@/lib/profile'
import { getVertical } from '@/lib/verticals'
import { tenantApprovalsApi } from '@/lib/tenant-approvals'
import { navigate } from '@/lib/router'
import { formatDate } from '@/lib/format'
import {
  ErrorBanner,
  FieldInput,
  FieldSelect,
  FieldTextarea,
  GhostButton,
  Notice,
  Panel,
  PrimaryButton,
  Toggle,
} from '@/components/remake/ui'
import { LoadingBlock } from '@/components/ui/feedback'
import { PageHeader } from '@/components/layout/page-header'
import { useAuth } from '@/lib/auth'
import { useToast } from '@/components/ui/toast'
import { useTenantDetail } from '@/components/tenants/hooks'

/** The compact size the legacy `size="sm"` buttons had in the header. */
const smallBtn = 'px-3 py-1.5 text-xs'

export type ProfileEditorMode = 'brand' | 'menu'

export function ProfileEditor({
  tenantId,
  mode = 'brand',
}: {
  tenantId: string
  /** brand = company Profile; menu = WhatsApp → Profile menu (hours + notifications). */
  mode?: ProfileEditorMode
}) {
  const detail = useTenantDetail(tenantId)
  const { identity, exitImpersonation, impersonating } = useAuth()
  const isSuperAdmin = identity?.role === 'super_admin'
  // View-only super admin, or customer_care after Onboarded users → Login.
  const canReviewPending = isSuperAdmin || impersonating
  // Tenant admin edits the profile here — saving writes a draft and every
  // publish (profile, menu, hours, intents) goes to super-admin approval.
  // The super admin is VIEW-ONLY inside a tenant (read-only mirror).
  // Support Login keeps write access (impersonating as the tenant admin).
  const readOnly = isSuperAdmin && !impersonating
  const action = useAction()
  const toast = useToast()
  const [form, setForm] = useState<EditorForm | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  // The profile is read-only until the admin explicitly opts in, so a stray
  // click on a switch or input cannot silently rewrite a live tenant.
  const [editing, setEditing] = useState(false)

  const pendingPublish = useAsync(
    (s) =>
      canReviewPending
        ? tenantApprovalsApi
            .allAsReviewer('pending', s)
            .then(
              (rows) =>
                rows.find(
                  (r) => r.tenant_id === tenantId && r.request_type === 'publish_profile',
                ) ?? null,
            )
        : Promise.resolve(null),
    [canReviewPending, tenantId],
  )

  // Prefer the pending draft (merged over the file baseline): it contains
  // every unpublished change from the register wizard, so this editor and
  // the wizard always edit the same working copy.
  const effective = detail.data?.pending ?? detail.data?.effective ?? null
  const baseline = useMemo(
    () => (effective ? JSON.stringify(editorToSnapshot(editorFromProfile(effective))) : ''),
    [effective],
  )

  useEffect(() => {
    if (effective) {
      setForm(editorFromProfile(effective))
      setDirty(false)
      setEditing(false)
      setWarnings([])
    }
  }, [effective, mode])

  if (detail.loading) return <LoadingBlock label="Loading the profile…" />
  if (detail.error) {
    return <ErrorBanner title="Could not load the profile" message={detail.error} />
  }
  if (!form || !effective) {
    return (
      <Notice tone="warn" title="No effective profile">
        The merged profile could not be built for this tenant. Fix the failing layer, or publish a valid draft
        from the versions screen.
      </Notice>
    )
  }

  const vertical = getVertical(effective.vertical)
  const patch = (values: Partial<EditorForm>) => {
    if (!editing) return
    setForm((f) => (f ? { ...f, ...values } : f))
    setDirty(true)
  }
  const current = JSON.stringify(editorToSnapshot(form))
  const title = mode === 'brand' ? 'Profile' : 'Profile menu'
  const description =
    mode === 'brand'
      ? isSuperAdmin
        ? "View-only. This is the tenant's brand data as their admin maintains it — changes come from the tenant's admin and are approved by you."
        : 'Company brand and contact details. Saving writes a draft; publishing validates it and swaps the live profile (changes go to a super admin for approval first).'
      : isSuperAdmin
        ? "View-only. Working hours and notification targets as the tenant's admin maintains them."
        : 'Working hours and notification targets. Saving writes a draft; publishing validates it and swaps the live profile (changes go to a super admin for approval first).'

  const saveDraft = async (thenPublish: boolean) => {
    if (mode === 'brand') {
      const contactErrors = editorContactErrors(form)
      if (contactErrors.length) {
        setWarnings(contactErrors)
        toast.push('Fix the contact details before saving.', 'error')
        return
      }
    }
    const saved = await action.run(() => tenantsApi.saveDraft(tenantId, editorToSnapshot(form)))
    if (!saved) return
    setWarnings(saved.validation ?? [])
    setDirty(false)
    if (!thenPublish) {
      toast.push('Draft saved. Nothing is live until you publish.')
      detail.reload()
      return
    }
    if ((saved.validation ?? []).length) {
      toast.push('Draft has validation warnings — review them before publishing.', 'error')
      setWarnings(saved.validation)
      return
    }
    const published = await action.run(() => tenantsApi.publish(tenantId))
    if (published) {
      if (published.status === 'pending_approval') {
        toast.push(published.message ?? 'Change sent for super admin approval.')
      } else {
        toast.push(`Published version ${published.version}`)
      }
      setEditing(false)
      detail.reload()
    }
  }

  return (
    <div>
      <PageHeader
        title={title}
        description={description}
        actions={
          readOnly ? undefined : editing ? (
            // Support Login keeps a fake UI role of super_admin, but the API
            // session is the tenant admin — always queue for confirmation.
            isSuperAdmin && !impersonating ? (
              <>
                <GhostButton
                  className={smallBtn}
                  disabled={action.busy}
                  onClick={() => saveDraft(false)}
                >
                  {action.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save draft
                </GhostButton>
                <PrimaryButton
                  className={smallBtn}
                  disabled={action.busy}
                  onClick={() => saveDraft(true)}
                >
                  {action.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Save & publish
                </PrimaryButton>
              </>
            ) : (
              <PrimaryButton
                className={smallBtn}
                disabled={action.busy}
                onClick={() => saveDraft(true)}
              >
                {action.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Submit for approval
              </PrimaryButton>
            )
          ) : (
            <PrimaryButton
              className={smallBtn}
              onClick={() => setEditing(true)}
            >
              <Pencil className="h-4 w-4" />
              Edit {mode === 'brand' ? 'profile' : 'profile menu'}
            </PrimaryButton>
          )
        }
        meta={
          <>
            <span className={`text-xs ${dirty ? 'text-attink' : 'text-txmuted'}`}>
              {readOnly
                ? 'View-only — changes come from the tenant\'s admin'
                : !editing
                  ? 'Read-only — click Edit to make changes'
                  : dirty
                    ? 'Unsaved changes'
                    : 'In sync with the live profile'}
            </span>
            <span className="text-xs text-txfaint">v{effective.vertical} · {vertical.label}</span>
          </>
        }
      />

      {action.error && <ErrorBanner title="Action failed" message={action.error} className="mb-4" />}
      {canReviewPending && pendingPublish.data && (
        <Notice tone="warn" title="Profile change awaiting your approval" className="mb-4">
          <p className="mb-2 text-sm">
            Submitted by <strong>{pendingPublish.data.requester_username}</strong>
            {pendingPublish.data.created_at
              ? ` on ${formatDate(pendingPublish.data.created_at)}`
              : ''}
            . The live profile is unchanged until you approve it.
          </p>
          {pendingPublish.data.summary && (
            <p className="mb-3 text-sm text-txmuted">{pendingPublish.data.summary}</p>
          )}
          <div className="flex flex-wrap gap-2">
            <PrimaryButton
              className={smallBtn}
              disabled={action.busy}
              onClick={() =>
                void action.run(async () => {
                  const result = await tenantApprovalsApi.decideAsReviewer(
                    pendingPublish.data!.id,
                    'approved',
                    '',
                  )
                  toast.push(result.message ?? 'Approved and applied.')
                  if (impersonating) {
                    await exitImpersonation('/onboarding-users')
                  } else {
                    pendingPublish.reload()
                    detail.reload()
                    navigate('/tenant-requests')
                  }
                  return result
                })
              }
            >
              {action.busy ? 'Approving…' : 'Approve and return to superadmin'}
            </PrimaryButton>
            <GhostButton
              className={smallBtn}
              disabled={action.busy}
              onClick={() => navigate('/tenant-requests')}
            >
              Open Business requests
            </GhostButton>
          </div>
        </Notice>
      )}
      {warnings.length > 0 && (
        <Notice tone="warn" title="Validation warnings" className="mb-4">
          <ul className="list-disc space-y-1 pl-4">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Notice>
      )}

      {mode === 'brand' ? (
        <Panel title="Brand">
          <p className="-mt-1 mb-4 text-sm text-txmuted">Company names and contact details used in menus and signatures.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <FieldInput label="Display name" disabled={!editing} value={form.displayName} onChange={(e) => patch({ displayName: e.target.value })} />
            <FieldInput label="Company name" disabled={!editing} value={form.brand.name} onChange={(e) => patch({ brand: { ...form.brand, name: e.target.value } })} />
            <FieldInput label="Bot name" disabled={!editing} value={form.brand.botName} onChange={(e) => patch({ brand: { ...form.brand, botName: e.target.value } })} />
            <FieldInput label="Tagline" disabled={!editing} value={form.brand.tagline} onChange={(e) => patch({ brand: { ...form.brand, tagline: e.target.value } })} />
            <FieldInput label="Website" disabled={!editing} value={form.brand.website} onChange={(e) => patch({ brand: { ...form.brand, website: e.target.value } })} />
            <FieldInput
              label="Support email"
              type="email"
              disabled={!editing}
              value={form.brand.supportEmail}
              onChange={(e) => patch({ brand: { ...form.brand, supportEmail: e.target.value } })}
            />
            <FieldInput
              label="Support phone"
              disabled={!editing}
              value={form.brand.supportPhone}
              error={
                editing && form.brand.supportPhone.trim() && !isValidPhone(form.brand.supportPhone)
                  ? 'Phone must be a country code followed by a 10-digit number, e.g. +91 98765 43210'
                  : undefined
              }
              onChange={(e) => patch({ brand: { ...form.brand, supportPhone: e.target.value } })}
            />
            <FieldInput
              label="Closing signature"
              disabled={!editing}
              value={form.brand.signature}
              onChange={(e) => patch({ brand: { ...form.brand, signature: e.target.value } })}
            />
          </div>
        </Panel>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Working hours">
            <p className="-mt-1 mb-4 text-sm text-txmuted">Working hours configuration.</p>
            <div className="space-y-4">
              <Toggle
                checked={form.businessHours.alwaysOpen}
                disabled={!editing}
                onChange={(alwaysOpen) => patch({ businessHours: { ...form.businessHours, alwaysOpen } })}
                label="Always open"
              />
              <div className="grid grid-cols-3 gap-3">
                <FieldSelect
                  label="Timezone"
                  disabled={!editing}
                  value={form.businessHours.timezone}
                  onChange={(e) => patch({ businessHours: { ...form.businessHours, timezone: e.target.value } })}
                >
                  <option value="">Select…</option>
                  {timezoneOptions(form.businessHours.timezone).map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </FieldSelect>
                <FieldInput
                  label="Opens"
                  type="time"
                  disabled={!editing || form.businessHours.alwaysOpen}
                  value={form.businessHours.open}
                  onChange={(e) => patch({ businessHours: { ...form.businessHours, open: e.target.value } })}
                />
                <FieldInput
                  label="Closes"
                  type="time"
                  disabled={!editing || form.businessHours.alwaysOpen}
                  value={form.businessHours.close}
                  onChange={(e) => patch({ businessHours: { ...form.businessHours, close: e.target.value } })}
                />
              </div>
              <FieldTextarea
                label="Out-of-hours message"
                rows={2}
                disabled={!editing}
                value={form.businessHours.outOfHoursMessage}
                onChange={(e) => patch({ businessHours: { ...form.businessHours, outOfHoursMessage: e.target.value } })}
              />
            </div>
          </Panel>

          <Panel title="Notifications">
            <p className="-mt-1 mb-4 text-sm text-txmuted">Where leads, quotes and handoffs are pushed.</p>
            <div className="space-y-4">
              <FieldInput
                label="Sales email"
                type="email"
                disabled={!editing}
                value={form.notifications.salesEmail}
                onChange={(e) => patch({ notifications: { ...form.notifications, salesEmail: e.target.value } })}
              />
              <FieldInput
                label="Support email"
                type="email"
                disabled={!editing}
                value={form.notifications.supportEmail}
                onChange={(e) => patch({ notifications: { ...form.notifications, supportEmail: e.target.value } })}
              />
            </div>
          </Panel>
        </div>
      )}

      <p className="mt-4 flex items-center gap-2 text-xs text-txmuted">
        <TriangleAlert className="h-3.5 w-3.5" />
        {current === baseline
          ? 'No changes yet.'
          : isSuperAdmin
            ? 'Unsaved changes will be written as a draft, not published.'
            : 'Unsaved changes stay a draft until you submit them for approval.'}
      </p>
    </div>
  )
}
