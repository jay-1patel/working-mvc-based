import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Building2,
  CalendarClock,
  Check,
  FileText,
  Loader2,
  MessageSquareText,
  Rocket,
} from 'lucide-react'
import {
  applyStagedToDraft,
  draftToSnapshot,
  EMAIL_RE,
  emptyDraft,
  isValidPhone,
  isValidPhoneInput,
  type WizardDraft,
} from '@/lib/profile'
import { useAction, useAsync } from '@/lib/hooks'
import { useAuth } from '@/lib/auth'
import { adminsApi, type OnboardingTenant } from '@/lib/admins'
import { useTenants } from '@/lib/tenants'
import { navigate } from '@/lib/router'
import { VERTICAL_CATALOG, getVertical } from '@/lib/verticals'
import { onboardingKitsApi } from '@/lib/uploads'
import {
  Card,
  ErrorBanner,
  FieldInput,
  FieldSelect,
  GhostButton,
  Notice,
  PrimaryButton,
} from '@/components/remake/ui'
import { PageHeader } from '@/components/layout/page-header'
import { useToast } from '@/components/ui/toast'
import { OnboardingKitWidget } from '@/components/onboarding/onboarding-kit-widget'
import { LoadingBlock } from '@/components/ui/feedback'

/** Set up chatbot: phone → company (signup tenant) → brand → kit upload/PDF. */
const ADMIN_STEPS = [
  { id: 'whatsapp', label: 'WhatsApp' },
  { id: 'tenant', label: 'Company' },
  { id: 'brand', label: 'Brand' },
  { id: 'documents', label: 'Documents' },
] as const

type StepId = (typeof ADMIN_STEPS)[number]['id']

export function RegisterWizard({ onSubmitted }: { onSubmitted?: () => void } = {}) {
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<WizardDraft>(emptyDraft)
  const [pdfFilled, setPdfFilled] = useState<string[]>([])
  const { reload } = useTenants()
  const { identity, refreshIdentity } = useAuth()
  const action = useAction()
  const toast = useToast()

  const isSuperAdmin = identity?.role === 'super_admin'
  const steps = ADMIN_STEPS
  const stepId = steps[step].id as StepId
  const assignedTenantId = String(identity?.tenant_id || '').trim()

  const tenantsReq = useAsync(
    (signal) =>
      !isSuperAdmin && identity?.role === 'admin' && assignedTenantId
        ? adminsApi.onboardingTenants(signal)
        : Promise.resolve([] as OnboardingTenant[]),
    [isSuperAdmin, identity?.role, assignedTenantId, identity?.username],
  )

  const availableTenants = tenantsReq.data ?? []
  const selectedTenant =
    availableTenants.find((t) => t.id === (draft.tenantId.trim() || assignedTenantId)) ??
    (assignedTenantId
      ? {
          id: assignedTenantId,
          slug: assignedTenantId,
          display_name: draft.displayName || draft.companyName || assignedTenantId,
          vertical: draft.vertical || 'generic',
          waba_phone_id: null,
        }
      : null)

  useEffect(() => {
    if (!assignedTenantId || tenantsReq.loading) return
    const t = availableTenants.find((row) => row.id === assignedTenantId)
    setDraft((d) => {
      if (
        d.tenantId === assignedTenantId &&
        d.companyName &&
        d.displayName &&
        d.vertical
      ) {
        return d
      }
      return {
        ...d,
        tenantId: assignedTenantId,
        companyName: d.companyName || t?.display_name || assignedTenantId,
        displayName: d.displayName || t?.display_name || assignedTenantId,
        vertical: d.vertical || t?.vertical || 'generic',
      }
    })
  }, [assignedTenantId, availableTenants, tenantsReq.loading])

  const patch = (values: Partial<WizardDraft>) => setDraft((d) => ({ ...d, ...values }))

  const applyStaged = (staged: Parameters<typeof applyStagedToDraft>[1]) => {
    setDraft((d) => {
      const { draft: next, filled } = applyStagedToDraft(d, staged)
      queueMicrotask(() => setPdfFilled(filled))
      return next
    })
  }

  const error = useMemo(
    () => validationError(stepId, draft, assignedTenantId),
    [stepId, draft, assignedTenantId],
  )

  const submit = async () => {
    const snapshot = draftToSnapshot(draft)
    const phone = draft.wabaPhoneId.trim()
    const staged = draft.stagedUpload
    const completed = await action.run(() =>
      adminsApi.firstLoginComplete({
        waba_phone_id: phone,
        mobile_number:
          isValidPhone(phone) || isValidPhoneInput(phone) ? phone : draft.supportPhone.trim(),
        snapshot: snapshot as unknown as Record<string, unknown>,
        lane: (staged?.extraction_mode === 'kit' ? 'kit' : 'any') as 'kit' | 'any',
        ...(staged
          ? { upload_draft: staged as unknown as Record<string, unknown> }
          : {}),
      }),
    )
    if (!completed) return

    if (completed.upload?.status === 'published') {
      toast.push('Document catalog published into your tenant.')
    } else if (completed.upload?.status === 'failed') {
      toast.push(
        'Tenant is live, but the document could not be published — upload it again from Knowledge.',
        'error',
      )
    }

    const liveTenant = completed.tenant_id || assignedTenantId
    toast.push(
      `${draft.displayName || draft.companyName || liveTenant} is live — your console is ready.`,
    )
    await refreshIdentity()
    reload()
    if (onSubmitted) onSubmitted()
    else navigate(`/tenants/${encodeURIComponent(liveTenant)}/overview`)
  }

  if (isSuperAdmin) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader
          title="Tenant setup"
          description="Company admins receive a tenant_id at signup. After login they open Set up chatbot to finish WhatsApp, company, and brand."
        />
        <Card>
          <div className="space-y-3 px-5 py-5">
            <Notice tone="info" title="Signup creates the tenant">
              Send2 signup stores username, id, password, and a unique tenant_id. The company admin
              then completes Set up chatbot on that same tenant.
            </Notice>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Set up your chatbot"
        description="Your tenant id was created at signup. Add WhatsApp, company details, brand contacts, then upload the kit PDF."
      />

      <ol className="mb-7 flex flex-wrap gap-1.5">
        {steps.map((s, index) => {
          const state = index === step ? 'current' : index < step ? 'done' : 'todo'
          return (
            <li key={s.id} className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => index < step && setStep(index)}
                disabled={index > step}
                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition ${
                  state === 'current'
                    ? 'bg-accsoft text-acc ring-1 ring-inset ring-line'
                    : state === 'done'
                      ? 'text-ok hover:text-ok'
                      : 'text-txmuted'
                }`}
              >
                {state === 'done' ? <Check className="h-3 w-3" /> : <span>{index + 1}</span>}
                {s.label}
              </button>
              {index < steps.length - 1 && <span className="text-txfaint">/</span>}
            </li>
          )
        })}
      </ol>

      <Card>
        {stepId === 'whatsapp' && <WhatsAppStep draft={draft} patch={patch} />}
        {stepId === 'tenant' && (
          <CompanyStep
            draft={draft}
            patch={patch}
            tenantId={assignedTenantId}
            loading={tenantsReq.loading}
            error={tenantsReq.error}
          />
        )}
        {stepId === 'brand' && <BrandStep draft={draft} patch={patch} />}
        {stepId === 'documents' && (
          <DocumentsStep
            draft={draft}
            tenant={selectedTenant}
            onStaged={applyStaged}
            pdfFilled={pdfFilled}
          />
        )}

        {action.error && (
          <div className="px-5 pb-4">
            <ErrorBanner title="Setup failed" message={action.error} />
          </div>
        )}

        <div className="flex items-center justify-between border-t border-linesoft px-5 py-4">
          <GhostButton disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </GhostButton>

          {step < steps.length - 1 ? (
            <PrimaryButton disabled={Boolean(error)} onClick={() => setStep((s) => s + 1)}>
              Continue
              <ArrowRight className="h-4 w-4" />
            </PrimaryButton>
          ) : (
            <PrimaryButton disabled={action.busy || Boolean(error)} onClick={() => void submit()}>
              {action.busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Rocket className="h-4 w-4" />
              )}
              Finish setup
            </PrimaryButton>
          )}
        </div>
      </Card>

      {error && step < steps.length - 1 && (
        <p className="mt-3 text-xs text-attink">{error}</p>
      )}
    </div>
  )
}

// ── steps ──────────────────────────────────────────────────────────────────

function StepShell({
  title,
  description,
  icon,
  children,
}: {
  title: string
  description: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <>
      <div className="border-b border-linesoft px-5 py-4">
        <h2 className="flex items-center gap-2 text-base font-semibold text-tx">
          <span className="text-txmuted">{icon}</span>
          {title}
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-txmuted">{description}</p>
      </div>
      <div className="space-y-5 px-5 py-5">{children}</div>
    </>
  )
}

interface StepProps {
  draft: WizardDraft
  patch: (values: Partial<WizardDraft>) => void
}

function WhatsAppStep({ draft, patch }: StepProps) {
  return (
    <StepShell
      title="WhatsApp phone number"
      description="The phone number routes inbound messages to your selected tenant."
      icon={<CalendarClock className="h-4 w-4" />}
    >
      <FieldInput
        label="WhatsApp phone number *"
        value={draft.wabaPhoneId}
        onChange={(e) => patch({ wabaPhoneId: e.target.value })}
        placeholder="+91 8000305305"
        inputMode="tel"
        hint="The WhatsApp number itself (+91 8000305305) or its 15-digit id from the Meta Business account (WABA)."
      />
    </StepShell>
  )
}

function CompanyStep({
  draft,
  patch,
  tenantId,
  loading,
  error,
}: StepProps & {
  tenantId: string
  loading: boolean
  error: string | null
}) {
  return (
    <StepShell
      title="Company and business field"
      description="Tenant id was stored at signup. Confirm company details and pick your business field."
      icon={<Building2 className="h-4 w-4" />}
    >
      {loading ? <LoadingBlock label="Loading tenant…" /> : null}
      {error ? <ErrorBanner message={error} /> : null}
      {!tenantId ? (
        <Notice tone="warn" title="No tenant assigned">
          Signup must create a tenant_id before Set up chatbot can continue.
        </Notice>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <FieldInput
            label="Company name *"
            value={draft.companyName}
            onChange={(e) =>
              patch({
                companyName: e.target.value,
                displayName: e.target.value,
              })
            }
            placeholder="Wanderly Travels"
          />
          <FieldInput
            label="Tenant id"
            value={tenantId}
            readOnly
            hint="Created at signup. Used in the API and database."
          />
          <FieldInput
            label="Display name"
            value={draft.displayName}
            onChange={(e) => patch({ displayName: e.target.value })}
            placeholder="Wanderly Travels"
          />
          <FieldInput
            label="Website"
            value={draft.website}
            onChange={(e) => patch({ website: e.target.value })}
            placeholder="https://example.com"
          />
          <div className="sm:col-span-2">
            <FieldSelect
              label="Business field *"
              value={draft.vertical}
              onChange={(e) => patch({ vertical: e.target.value })}
              hint="Selects profile defaults and intents for your bot."
            >
              {VERTICAL_CATALOG.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </FieldSelect>
          </div>
        </div>
      )}
    </StepShell>
  )
}

function BrandStep({ draft, patch }: StepProps) {
  return (
    <StepShell
      title="Brand and support contacts"
      description="How the bot introduces itself and how customers reach support."
      icon={<MessageSquareText className="h-4 w-4" />}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldInput
          label="Bot name *"
          value={draft.botName}
          onChange={(e) => patch({ botName: e.target.value })}
          placeholder="Asha"
        />
        <FieldInput
          label="Tagline"
          value={draft.tagline}
          onChange={(e) => patch({ tagline: e.target.value })}
          placeholder="Software that ships"
        />
        <FieldInput
          label="Support email *"
          type="email"
          value={draft.supportEmail}
          onChange={(e) => patch({ supportEmail: e.target.value })}
          placeholder="support@example.com"
        />
        <FieldInput
          label="Support phone *"
          value={draft.supportPhone}
          onChange={(e) => patch({ supportPhone: e.target.value })}
          placeholder="+91 98765 43210"
          inputMode="tel"
          error={
            draft.supportPhone.trim() && !isValidPhone(draft.supportPhone)
              ? 'Phone must be a country code followed by 10 digits, e.g. +91 98765 43210'
              : undefined
          }
        />
      </div>
    </StepShell>
  )
}

function DocumentsStep({
  draft,
  tenant,
  onStaged,
  pdfFilled,
}: {
  draft: WizardDraft
  tenant: OnboardingTenant | null
  onStaged: (staged: Parameters<typeof applyStagedToDraft>[1]) => void
  pdfFilled: string[]
}) {
  const vertical = tenant?.vertical || draft.vertical || 'generic'
  const v = getVertical(vertical)
  const staged = draft.stagedUpload
  const offeringCount = staged?.offerings?.length ?? 0
  const faqCount = staged?.faqs?.length ?? 0

  return (
    <StepShell
      title="Predefined files"
      description={`Download the ${v.label} kit PDF for this tenant, fill it, then upload it here.`}
      icon={<FileText className="h-4 w-4" />}
    >
      {!tenant ? (
        <Notice tone="warn" title="Tenant missing">
          Signup must assign a tenant_id before the kit PDF can be shown.
        </Notice>
      ) : (
        <>
          <Notice tone="info" title={tenant.display_name}>
            Tenant <strong>{tenant.id}</strong> · {v.label}. Download the predefined PDF below,
            then upload the filled file.
          </Notice>
          <OnboardingKitWidget
            tenantId={tenant.id}
            vertical={vertical}
            mode="onboarding"
            kitOnly
            onStagedDraft={onStaged}
          />
          {(staged || pdfFilled.length > 0) && (
            <Notice tone="success" title="Document ready" className="mt-2">
              {pdfFilled.length > 0 && (
                <p className="text-xs text-tx">
                  Filled in: {pdfFilled.join(', ')}
                  {offeringCount || faqCount
                    ? ` · ${offeringCount} offerings · ${faqCount} FAQs`
                    : ''}
                </p>
              )}
            </Notice>
          )}
          <div className="rounded-lg border border-line bg-paper px-4 py-3 text-xs text-txmuted">
            <p className="flex items-center gap-1.5 font-medium text-tx">
              <BadgeCheck className="h-3.5 w-3.5 text-ok" />
              Finish setup publishes WhatsApp and brand on{' '}
              <span className="font-mono">{tenant.id}</span>
            </p>
          </div>
        </>
      )}
    </StepShell>
  )
}

function validationError(
  stepId: StepId,
  draft: WizardDraft,
  assignedTenantId: string,
): string | null {
  switch (stepId) {
    case 'whatsapp': {
      if (!draft.wabaPhoneId.trim()) return 'A WhatsApp phone number (or its id) is required.'
      const phoneDigits = draft.wabaPhoneId.replace(/\D/g, '')
      const isMetaId = /^\d{15,16}$/.test(phoneDigits)
      const isPhoneNumber = isValidPhone(draft.wabaPhoneId) || isValidPhoneInput(draft.wabaPhoneId)
      if (!isMetaId && !isPhoneNumber) {
        return 'Enter a valid 10-digit WhatsApp phone number (e.g. +91 98765 43210) or its 15-digit ID from Meta.'
      }
      return null
    }
    case 'tenant': {
      if (!assignedTenantId) return 'No tenant assigned from signup.'
      if (!draft.companyName.trim()) return 'Company name is required.'
      if (!draft.vertical.trim()) return 'Pick a business field.'
      return null
    }
    case 'brand': {
      if (!draft.botName.trim()) return 'Give the bot a name.'
      if (!draft.supportEmail.trim()) return 'A support email is required.'
      if (!EMAIL_RE.test(draft.supportEmail.trim())) return 'The support email does not look valid.'
      if (!draft.supportPhone.trim()) return 'A support phone number is required.'
      if (!isValidPhone(draft.supportPhone)) {
        return 'The support phone must be a country code followed by a 10-digit number, e.g. +91 98765 43210.'
      }
      return null
    }
    case 'documents':
      return null
    default:
      return null
  }
}
