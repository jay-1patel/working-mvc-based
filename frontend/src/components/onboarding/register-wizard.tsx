import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Building2,
  CalendarClock,
  Check,
  Loader2,
  MessageSquareText,
  Rocket,
  Sparkles,
  Webhook,
} from 'lucide-react'
import {
  applyStagedToDraft,
  applyVertical,
  draftToSnapshot,
  EMAIL_RE,
  emptyDraft,
  isValidBrochureUrl,
  isValidPhone,
  isValidPhoneInput,
  slugify,
  timezoneOptions,
  URL_RE,
  type WizardDraft,
} from '@/lib/profile'
import { useAction } from '@/lib/hooks'
import { useAuth } from '@/lib/auth'
import { adminsApi } from '@/lib/admins'
import { useTenants } from '@/lib/tenants'
import { navigate } from '@/lib/router'
import { VERTICAL_CATALOG, getVertical } from '@/lib/verticals'
import { onboardingKitsApi } from '@/lib/uploads'
import {
  Card,
  ErrorBanner,
  FieldInput,
  FieldSelect,
  FieldTextarea,
  GhostButton,
  Notice,
  Panel,
  PrimaryButton,
  TagField,
  Toggle,
} from '@/components/remake/ui'
import { VerticalGlyph } from '@/components/vertical-icon'
import { PageHeader } from '@/components/layout/page-header'
import { useToast } from '@/components/ui/toast'
import { OnboardingKitWidget } from '@/components/onboarding/onboarding-kit-widget'

const DAYS = [
  { value: 1, label: 'Mon' },
  { value: 2, label: 'Tue' },
  { value: 3, label: 'Wed' },
  { value: 4, label: 'Thu' },
  { value: 5, label: 'Fri' },
  { value: 6, label: 'Sat' },
  { value: 0, label: 'Sun' },
]

const fieldLabelClass = 'mb-1.5 block text-sm font-medium text-tx'

// First-login admin setup: WhatsApp → company/vertical → profile → go live.
// Credentials come from Send2; the admin creates their own tenant here.
const ADMIN_STEPS = [
  { id: 'whatsapp', label: 'WhatsApp' },
  { id: 'company', label: 'Company' },
  { id: 'brand', label: 'Brand & voice' },
  { id: 'domain', label: 'Your business' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'review', label: 'Review' },
] as const

type StepId = (typeof ADMIN_STEPS)[number]['id']

export function RegisterWizard({ onSubmitted }: { onSubmitted?: () => void } = {}) {
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<WizardDraft>(emptyDraft)
  const [pdfFilled, setPdfFilled] = useState<string[]>([])
  const { reload, tenants } = useTenants()
  const { identity, refreshIdentity } = useAuth()
  const action = useAction()
  const toast = useToast()

  const isSuperAdmin = identity?.role === 'super_admin'
  const steps = ADMIN_STEPS
  const stepId = steps[step].id as StepId

  const patch = (values: Partial<WizardDraft>) => setDraft((d) => ({ ...d, ...values }))

  const applyStaged = (staged: Parameters<typeof applyStagedToDraft>[1]) => {
    setDraft((d) => {
      const { draft: next, filled } = applyStagedToDraft(d, staged)
      queueMicrotask(() => setPdfFilled(filled))
      return next
    })
  }

  // Match registry id/slug only (same rules as backend find_registry_conflict).
  const tenantIdTaken = (() => {
    const id = draft.tenantId.trim()
    if (!id) return false
    const norm = (v: string) => v.toLowerCase().replace(/[-_\s]/g, '')
    const n = norm(id)
    return tenants.some((t) => {
      const tid = String(t.id || '')
      const slug = String(t.slug || '')
      return (
        tid === id ||
        slug === id ||
        tid.toLowerCase() === id.toLowerCase() ||
        slug.toLowerCase() === id.toLowerCase() ||
        norm(tid) === n ||
        norm(slug) === n
      )
    })
  })()
  const companyNameTaken = (() => {
    const name = (draft.displayName || draft.companyName).trim().toLowerCase().replace(/\s+/g, ' ')
    if (!name) return false
    return tenants.some((t) => {
      const existing = String(t.display_name || '').trim().toLowerCase().replace(/\s+/g, ' ')
      return existing === name && String(t.id) !== draft.tenantId.trim()
    })
  })()
  const error = useMemo(
    () => validationError(stepId, draft, tenantIdTaken, companyNameTaken),
    [stepId, draft, tenantIdTaken, companyNameTaken],
  )

  const submit = async () => {
    const id = draft.tenantId.trim()
    const snapshot = draftToSnapshot(draft)
    const phone = draft.wabaPhoneId.trim()
    const staged = draft.stagedUpload
    const completed = await action.run(() =>
      adminsApi.firstLoginComplete({
        tenant_id: id,
        slug: id,
        vertical: draft.vertical,
        display_name: draft.displayName || draft.companyName,
        website: draft.website.trim(),
        waba_phone_id: phone,
        mobile_number: isValidPhone(phone) || isValidPhoneInput(phone) ? phone : draft.supportPhone.trim(),
        snapshot: snapshot as unknown as Record<string, unknown>,
      }),
    )
    if (!completed) return

    // Publish brochure / kit extraction into the new tenant (offerings, FAQ, KB).
    if (staged) {
      try {
        await onboardingKitsApi.publishTenant(completed.tenant_id, {
          ...staged,
          tenant_id: completed.tenant_id,
        })
        toast.push('Document catalog published into your tenant.')
      } catch (err) {
        console.error('Onboarding document publish failed:', err)
        toast.push(
          'Tenant is live, but the document could not be published — upload it again from Knowledge.',
          'error',
        )
      }
    }

    toast.push(`${draft.companyName} is live — your console is ready.`)
    await refreshIdentity()
    reload()
    if (onSubmitted) onSubmitted()
    else navigate(`/tenants/${encodeURIComponent(completed.tenant_id)}/overview`)
  }

  if (isSuperAdmin) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader
          title="Tenant setup"
          description="Company admins create their own tenant on first login. Provision their Send2 username and session id from Team — do not register tenants here."
        />
        <Card>
          <div className="space-y-3 px-5 py-5">
            <Notice tone="info" title="First-login is self-serve">
              Create an admin account with no tenant assigned. When they log in they add WhatsApp,
              pick their business field (for example IT / Software), and go live. Menus and privileges
              follow that field — retail sees Orders; IT does not.
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
        description="Add your WhatsApp number, company details, and business field. When you finish, your console opens with the menus that match that field."
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
        {stepId === 'company' && <CompanyStep draft={draft} patch={patch} />}
        {stepId === 'brand' && <BrandStep draft={draft} patch={patch} />}
        {stepId === 'domain' && (
          <DomainStep draft={draft} patch={patch} onStaged={applyStaged} pdfFilled={pdfFilled} />
        )}
        {stepId === 'notifications' && <NotificationsStep draft={draft} patch={patch} />}
        {stepId === 'review' && (
          <ReviewStep draft={draft} onEdit={setStep} pdfFilled={pdfFilled} />
        )}

        {action.error && (
          <div className="px-5 pb-4">
            <ErrorBanner title="Setup failed" message={action.error} />
          </div>
        )}

        <div className="flex items-center justify-between border-t border-linesoft px-5 py-4">
          <GhostButton
            disabled={step === 0}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </GhostButton>

          {step < steps.length - 1 ? (
            <PrimaryButton
              disabled={Boolean(error)}
              onClick={() => setStep((s) => s + 1)}
            >
              Continue
              <ArrowRight className="h-4 w-4" />
            </PrimaryButton>
          ) : (
            <PrimaryButton
              disabled={action.busy || Boolean(error)}
              onClick={submit}
            >
              {action.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
              Finish setup
            </PrimaryButton>
          )}
        </div>
      </Card>

      {error && step < steps.length - 1 && (
        <p className="mt-3 text-xs text-attink">{error}</p>
      )}
      {tenantIdTaken && stepId === 'company' && (
        <Notice tone="warn" className="mt-4">
          A tenant with this id already exists. Pick another id.
        </Notice>
      )}
      {companyNameTaken && stepId === 'company' && (
        <Notice tone="warn" className="mt-4">
          A tenant with this company name already exists. Choose a different name.
        </Notice>
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

function CompanyStep({ draft, patch }: StepProps) {
  return (
    <StepShell
      title="Company and business field"
      description="Name your company and pick the field you belong to (for example IT / Software or Retail). That choice sets which menus and privileges you get — Orders only appear for retail-style businesses."
      icon={<Building2 className="h-4 w-4" />}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldInput
          label="Company name"
          value={draft.companyName}
          onChange={(e) => patch({ companyName: e.target.value, tenantId: draft.tenantId || slugify(e.target.value) })}
          placeholder="Leeway Softech"
          required
        />
        <FieldInput
          label="Tenant id"
          value={draft.tenantId}
          onChange={(e) => patch({ tenantId: slugify(e.target.value) })}
          hint="Lowercase, no spaces. This is the id used in the API and the database."
          required
        />
        <FieldInput
          label="Display name"
          value={draft.displayName}
          onChange={(e) => patch({ displayName: e.target.value })}
          placeholder={draft.companyName || 'Shown in menus'}
        />
        <FieldInput
          label="Website"
          value={draft.website}
          onChange={(e) => patch({ website: e.target.value })}
          placeholder="https://example.com"
        />
      </div>

      <div>
        <p className={fieldLabelClass}>Business field</p>
        <p className="mb-2 text-xs text-txfaint">
          This is the single most important answer: it selects the profile defaults, the vocabulary, the menu and the intents.
        </p>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {VERTICAL_CATALOG.map((v) => {
            const active = draft.vertical === v.id
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => patch(applyVertical(draft, v.id))}
                className={`flex gap-3 rounded-lg p-3.5 text-left ring-1 ring-inset transition ${
                  active
                    ? 'bg-accsoft ring-acc'
                    : 'bg-paper ring-line hover:bg-accsoft'
                }`}
              >
                <VerticalGlyph
                  name={v.icon}
                  className={`mt-0.5 h-5 w-5 shrink-0 ${active ? 'text-acc' : 'text-txmuted'}`}
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-tx">{v.label}</span>
                  <span className="mt-1 block text-xs leading-relaxed text-txmuted">{v.blurb}</span>
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </StepShell>
  )
}

function WhatsAppStep({ draft, patch }: StepProps) {
  const toggleDay = (day: number) =>
    patch({
      openDays: draft.openDays.includes(day)
        ? draft.openDays.filter((d) => d !== day)
        : [...draft.openDays, day].sort(),
    })

  return (
    <StepShell
      title="WhatsApp and working hours"
      description="The phone number routes inbound messages to this tenant. Working hours decide when the bot offers a callback instead of a live handoff."
      icon={<CalendarClock className="h-4 w-4" />}
    >
      <FieldInput
        label="WhatsApp phone number *"
        value={draft.wabaPhoneId}
        onChange={(e) => patch({ wabaPhoneId: e.target.value })}
        placeholder="+91 8000305305"
        inputMode="tel"
        hint="The WhatsApp number itself (+91 8000305305) or its 15-digit id from the Meta Business account (WABA). Each number belongs to exactly one tenant."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <FieldSelect
          label="Timezone *"
          value={draft.timezone}
          onChange={(e) => patch({ timezone: e.target.value })}
          hint="Used by out-of-hours and callback logic."
        >
          <option value="">Select…</option>
          {timezoneOptions(draft.timezone).map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </FieldSelect>
        <FieldInput
          label="Opens"
          type="time"
          value={draft.openTime}
          onChange={(e) => patch({ openTime: e.target.value })}
          disabled={draft.alwaysOpen}
        />
        <FieldInput
          label="Closes"
          type="time"
          value={draft.closeTime}
          onChange={(e) => patch({ closeTime: e.target.value })}
          disabled={draft.alwaysOpen}
        />
      </div>

      <Toggle
        checked={draft.alwaysOpen}
        onChange={(alwaysOpen) => patch({ alwaysOpen })}
        label="Always open"
        description="When off, out-of-hours conversations get a callback flow instead of a handoff."
      />

      {!draft.alwaysOpen && (
        <div className="space-y-3">
          <div>
            <p className={fieldLabelClass}>Open on</p>
            <div className="flex flex-wrap gap-1.5">
              {DAYS.map((day) => {
                const on = draft.openDays.includes(day.value)
                return (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => toggleDay(day.value)}
                    className={`h-9 w-12 rounded-lg text-xs font-medium ring-1 ring-inset transition ${
                      on
                        ? 'bg-acc text-onacc ring-acc'
                        : 'bg-card text-txmuted ring-line hover:text-tx'
                    }`}
                  >
                    {day.label}
                  </button>
                )
              })}
            </div>
          </div>
          <FieldTextarea
            label="Out-of-hours message"
            value={draft.outOfHoursMessage}
            onChange={(e) => patch({ outOfHoursMessage: e.target.value })}
          />
        </div>
      )}
    </StepShell>
  )
}

function BrandStep({ draft, patch }: StepProps) {
  const v = getVertical(draft.vertical)
  return (
    <StepShell
      title="Brand and voice"
      description="How the bot introduces itself. These strings are used in menus and prompts; the business field sets the default speaking style."
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
          label="Closing signature"
          value={draft.signature}
          onChange={(e) => patch({ signature: e.target.value })}
          placeholder="— Team Leeway"
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
              ? 'Phone must be a 10-digit number (or country code followed by 10 digits, e.g. +91 98765 43210)'
              : undefined
          }
          hint="Country code followed by a 10-digit number, e.g. +91 98765 43210."
        />
      </div>

      <FieldTextarea
        label="Menu greeting"
        value={draft.greeting}
        onChange={(e) => patch({ greeting: e.target.value })}
        placeholder={`Hi! I'm ${draft.botName || 'the assistant'} from ${draft.companyName || 'our team'}. How can I help?`}
        hint="Shown as the WhatsApp menu body. Leave blank to use the field default."
      />

      <Notice tone="info" title={`Vocabulary for ${v.short}`}>
        The bot will call your offerings <strong>{v.nouns.item}</strong> and your enquiries{' '}
        <strong>{v.nouns.lead}</strong>. You can override every one of these later in the profile editor.
      </Notice>
    </StepShell>
  )
}

function DomainStep({
  draft,
  patch,
  onStaged,
  pdfFilled,
}: StepProps & {
  onStaged: (staged: Parameters<typeof applyStagedToDraft>[1]) => void
  pdfFilled: string[]
}) {
  const v = getVertical(draft.vertical)
  const hasQuestions = v.questions.length > 0
  const missingRequired = v.questions.filter((q) => q.required && !answerValue(draft, q.key))
  const staged = draft.stagedUpload
  const offeringCount = staged?.offerings?.length ?? 0
  const faqCount = staged?.faqs?.length ?? 0

  return (
    <StepShell
      title={`About your ${v.short.toLowerCase()} business`}
      description={
        hasQuestions
          ? 'These answers become the words the bot recognises. The more specific you are, the fewer questions it gets wrong.'
          : `Upload a brochure or company PDF to fill ${v.nouns.item}, FAQs and menu. Safety and handoff stay AI-driven from each customer message.`
      }
      icon={<Sparkles className="h-4 w-4" />}
    >
      <Panel title="Company document">
        <p className="-mt-1 mb-4 text-sm text-txmuted">
          Download the tenant demo PDF, fill it, then upload — or upload your own brochure. Extracted{' '}
          {v.nouns.item} and FAQs publish when you finish setup.
        </p>
        <OnboardingKitWidget
          vertical={draft.vertical}
          mode="onboarding"
          onStagedDraft={onStaged}
        />
        {(staged || pdfFilled.length > 0) && (
          <Notice
            tone="success"
            title={
              staged?.extraction_mode === 'kit'
                ? 'Fetched from your document'
                : 'Started from your document'
            }
            className="mt-4"
          >
            {pdfFilled.length > 0 && (
              <p className="text-xs text-tx">
                Filled in: {pdfFilled.join(', ')}
                {offeringCount || faqCount
                  ? ` · ${offeringCount} ${v.nouns.item}${offeringCount === 1 ? '' : ''} · ${faqCount} FAQ${faqCount === 1 ? '' : 's'}`
                  : ''}
              </p>
            )}
            {pdfFilled.length === 0 && (offeringCount > 0 || faqCount > 0) && (
              <p className="text-xs text-tx">
                Ready: {offeringCount} {v.nouns.item}
                {offeringCount === 1 ? '' : ''} · {faqCount} FAQ{faqCount === 1 ? '' : 's'}
              </p>
            )}
          </Notice>
        )}
      </Panel>

      {hasQuestions ? (
        <div className="space-y-5">
          {v.questions.map((q) => {
            const value = draft.answers[q.key]
            return (
              <div key={q.key}>
                <p className={fieldLabelClass}>
                  {q.label}
                  {q.required && <span className="ml-1 text-badink">*</span>}
                </p>
                {q.kind === 'chips' && (
                  <TagField
                    value={Array.isArray(value) ? value : []}
                    onChange={(next) => patch({ answers: { ...draft.answers, [q.key]: next } })}
                    suggestions={q.suggestions ?? []}
                  />
                )}
                {q.kind === 'text' && (
                  <FieldInput
                    value={typeof value === 'string' ? value : ''}
                    onChange={(e) => patch({ answers: { ...draft.answers, [q.key]: e.target.value } })}
                    placeholder={q.placeholder}
                  />
                )}
                {q.kind === 'textarea' && (
                  <FieldTextarea
                    value={typeof value === 'string' ? value : ''}
                    onChange={(e) => patch({ answers: { ...draft.answers, [q.key]: e.target.value } })}
                    placeholder={q.placeholder}
                  />
                )}
                {q.kind === 'select' && (
                  <FieldSelect
                    value={typeof value === 'string' ? value : ''}
                    onChange={(e) => patch({ answers: { ...draft.answers, [q.key]: e.target.value } })}
                  >
                    <option value="">Select…</option>
                    {(q.options ?? []).map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </FieldSelect>
                )}
                {q.help && <p className="mt-1.5 text-xs leading-relaxed text-txmuted">{q.help}</p>}
              </div>
            )
          })}
        </div>
      ) : null}

      <Panel title="Optional modules">
        <p className="-mt-1 mb-4 text-sm text-txmuted">
          Switch on only what this {v.short.toLowerCase()} company will use — anything off stays hidden from their console.
        </p>
        <div className="space-y-4">
          {v.optionalModules.map(({ flag, label, description }) => (
            <Toggle
              key={flag}
              checked={draft.features.includes(flag)}
              onChange={(on) =>
                patch({
                  features: on
                    ? [...draft.features.filter((f) => f !== flag), flag]
                    : draft.features.filter((f) => f !== flag),
                })
              }
              label={label}
              description={description}
            />
          ))}
        </div>
      </Panel>

      {missingRequired.length > 0 && (
        <Notice tone="warn">
          Answer {missingRequired.map((q) => q.label).join(', ')} before continuing.
        </Notice>
      )}
    </StepShell>
  )
}

function NotificationsStep({ draft, patch }: StepProps) {
  return (
    <StepShell
      title="Where do enquiries go?"
      description="Leads, quotes and handoffs are pushed to these destinations. A tenant with no destination configured will collect leads that nobody reads."
      icon={<Webhook className="h-4 w-4" />}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldInput
          label="Sales / enquiries email *"
          type="email"
          value={draft.salesEmail}
          onChange={(e) => patch({ salesEmail: e.target.value })}
          placeholder="sales@example.com"
        />
        <FieldInput
          label="Support email"
          type="email"
          value={draft.notificationsSupportEmail}
          onChange={(e) => patch({ notificationsSupportEmail: e.target.value })}
          placeholder="support@example.com"
        />
      </div>
    </StepShell>
  )
}

function ReviewStep({
  draft,
  onEdit,
  pdfFilled,
}: {
  draft: WizardDraft
  onEdit: (step: number) => void
  pdfFilled: string[]
}) {
  const v = getVertical(draft.vertical)
  const answers = Object.entries(draft.answers).filter(([, value]) =>
    Array.isArray(value) ? value.length : Boolean(value),
  )
  const staged = draft.stagedUpload
  const docSummary = staged
    ? [
        `${staged.offerings?.length ?? 0} ${v.nouns.item}`,
        `${staged.faqs?.length ?? 0} FAQs`,
        pdfFilled.length ? `filled: ${pdfFilled.join(', ')}` : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : 'none uploaded'

  // Step indices match ADMIN_STEPS: whatsapp=0, company=1, brand=2, domain=3, ...
  const rows: { label: string; value: React.ReactNode; step: number }[] = [
    { label: 'WhatsApp', value: draft.wabaPhoneId || 'not bound', step: 0 },
    {
      label: 'Working hours',
      value: draft.alwaysOpen
        ? 'Always open'
        : `${draft.openTime}–${draft.closeTime} · ${draft.timezone} · ${draft.openDays.length} day(s)`,
      step: 0,
    },
    { label: 'Company', value: draft.companyName || '—', step: 1 },
    { label: 'Tenant id', value: draft.tenantId || '—', step: 1 },
    { label: 'Field', value: v.label, step: 1 },
    { label: 'Website', value: draft.website || '—', step: 1 },
    { label: 'Bot name', value: draft.botName || v.label, step: 2 },
    { label: 'Support', value: [draft.supportEmail, draft.supportPhone].filter(Boolean).join(' · ') || '—', step: 2 },
    { label: 'Calls it', value: v.nouns.item, step: 2 },
    {
      label: 'Document',
      value: docSummary,
      step: 3,
    },
    {
      label: 'Business answers',
      value: answers.length ? (
        <ul className="space-y-1">
          {answers.map(([key, value]) => (
            <li key={key} className="text-xs text-tx">
              <span className="text-txfaint">{key.replace(/_/g, ' ')}:</span>{' '}
              {Array.isArray(value) ? value.join(', ') : value}
            </li>
          ))}
        </ul>
      ) : (
        '—'
      ),
      step: 3,
    },
    {
      label: 'Notifications',
      value:
        [draft.salesEmail, draft.notificationsSupportEmail].filter(Boolean).join(' · ') ||
        'none configured',
      step: 4,
    },
  ]

  return (
    <StepShell
      title="Review and go live"
      description={`Finishing creates your tenant, publishes version 1 with the ${v.short} defaults, and opens your console. Menus follow the business field you chose.`}
      icon={<BadgeCheck className="h-4 w-4" />}
    >
      <div className="divide-y divide-linesoft rounded-panel border border-line">
        {rows.map((row) => (
          <div key={row.label} className="flex items-start gap-4 px-4 py-3">
            <span className="w-40 shrink-0 text-xs text-txfaint">{row.label}</span>
            <span className="min-w-0 flex-1 text-xs text-tx">
              {typeof row.value === 'string' ? row.value : row.value}
            </span>
            <button
              type="button"
              onClick={() => onEdit(row.step)}
              className="shrink-0 text-xs text-acc transition hover:opacity-80"
            >
              Edit
            </button>
          </div>
        ))}
      </div>
    </StepShell>
  )
}

// ── helpers ────────────────────────────────────────────────────────────────

interface StepProps {
  draft: WizardDraft
  patch: (values: Partial<WizardDraft>) => void
}

function answerValue(draft: WizardDraft, key: string): string {
  const value = draft.answers[key]
  if (Array.isArray(value)) return value.join(', ')
  return typeof value === 'string' ? value : ''
}

function validationError(
  stepId: StepId,
  draft: WizardDraft,
  idTaken: boolean,
  companyNameTaken = false,
): string | null {
  switch (stepId) {
    case 'company':
      if (!draft.companyName.trim()) return 'A company name is required.'
      if (!draft.tenantId.trim()) return 'A tenant id is required.'
      if (!draft.vertical.trim()) return 'Pick the business field you belong to.'
      if (idTaken) return 'That tenant id is already registered.'
      if (companyNameTaken) return 'That company name is already used by another tenant.'
      if (draft.website.trim() && !URL_RE.test(draft.website.trim()))
        return 'The website does not look like a valid URL (e.g. https://example.com).'
      return null
    case 'whatsapp': {
      if (!draft.wabaPhoneId.trim()) return 'A WhatsApp phone number (or its id) is required.'
      const phoneDigits = draft.wabaPhoneId.replace(/\D/g, '')
      const isMetaId = /^\d{15,16}$/.test(phoneDigits)
      const isPhoneNumber = isValidPhone(draft.wabaPhoneId) || isValidPhoneInput(draft.wabaPhoneId)
      if (!isMetaId && !isPhoneNumber)
        return 'Enter a valid 10-digit WhatsApp phone number (e.g. +91 98765 43210) or its 15-digit ID from Meta.'
      if (!draft.timezone.trim()) return 'Select a timezone.'
      if (!draft.alwaysOpen && draft.openDays.length === 0) return 'Pick at least one working day.'
      return null
    }
    case 'brand': {
      if (!draft.botName.trim()) return 'Give the bot a name.'
      if (!draft.supportEmail.trim()) return 'A support email is required.'
      if (!EMAIL_RE.test(draft.supportEmail.trim()))
        return 'The support email does not look valid.'
      if (!draft.supportPhone.trim()) return 'A support phone number is required.'
      if (!isValidPhone(draft.supportPhone))
        return 'The support phone must be a country code followed by a 10-digit number, e.g. +91 98765 43210.'
      return null
    }
    case 'domain': {
      const v = getVertical(draft.vertical)
      const missing = v.questions.filter((q) => q.required && !answerValue(draft, q.key))
      if (missing.length) return `Still needed: ${missing.map((q) => q.label).join(', ')}.`
      return null
    }
    case 'notifications': {
      if (!draft.salesEmail.trim()) return 'A sales / enquiries email is required — leads need a destination.'
      if (!EMAIL_RE.test(draft.salesEmail.trim()))
        return 'The sales / enquiries email does not look valid.'
      if (draft.notificationsSupportEmail.trim() && !EMAIL_RE.test(draft.notificationsSupportEmail.trim()))
        return 'The notifications support email does not look valid.'
      if (draft.brochureUrl.trim() && !isValidBrochureUrl(draft.brochureUrl))
        return 'The brochure URL does not look like a valid URL (use https://…, http://IP/…, or /uploaded_files/…).'
      for (const channel of draft.channels) {
        if (!channel.to.trim()) continue
        if (channel.type === 'email' && !EMAIL_RE.test(channel.to.trim()))
          return 'A notification channel email destination does not look valid.'
        if (channel.type === 'webhook' && !URL_RE.test(channel.to.trim()))
          return 'A notification channel webhook destination does not look like a valid URL.'
      }
      return null
    }
    default:
      return null
  }
}
