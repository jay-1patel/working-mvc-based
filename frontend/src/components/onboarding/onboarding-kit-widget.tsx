import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Download,
  FileText,
  FolderUp,
  Loader2,
  Sparkles,
  ChevronDown,
  Files,
} from 'lucide-react'
import {
  onboardingKitsApi,
  type OnboardingTemplate,
  type StagedOnboardingDraft,
} from '@/lib/uploads'
import { useTenants } from '@/lib/tenants'
import { getVertical } from '@/lib/verticals'
import { GhostButton, Notice, PrimaryButton } from '@/components/remake/ui'
import { useToast } from '@/components/ui/toast'
import { OnboardingReviewModal } from './onboarding-review-modal'

interface OnboardingKitWidgetProps {
  tenantId?: string
  /** Lock example kit downloads to this vertical (overrides tenant lookup). */
  vertical?: string
  onStagedDraft?: (draft: StagedOnboardingDraft) => void
  onPublished?: (summary: any) => void
  compact?: boolean
  /** Hide the "Option A — Any document" lane; kit upload only. */
  kitOnly?: boolean
  /**
   * `ongoing` = post-onboarding Knowledge page: lead with “upload another PDF”
   * so admins can keep adding docs after the first setup.
   */
  mode?: 'onboarding' | 'ongoing'
}

type UploadLane = 'any' | 'kit'

export function OnboardingKitWidget({
  tenantId,
  vertical: verticalProp,
  onStagedDraft,
  onPublished,
  kitOnly,
  mode = 'onboarding',
}: OnboardingKitWidgetProps) {
  const ongoing = mode === 'ongoing'
  const toast = useToast()
  const { tenants } = useTenants()
  const anyFileRef = useRef<HTMLInputElement>(null)
  const kitFileRef = useRef<HTMLInputElement>(null)

  const tenantVertical = useMemo(() => {
    if (verticalProp) return verticalProp
    if (!tenantId) return null
    return tenants.find((t) => t.id === tenantId)?.vertical || null
  }, [verticalProp, tenantId, tenants])

  /** When scoped to a tenant, only that vertical's example kit is offered. */
  const lockToTenantVertical = Boolean(tenantVertical && tenantId)

  const [templates, setTemplates] = useState<OnboardingTemplate[]>([])
  const [selectedVertical, setSelectedVertical] = useState<string>(
    tenantVertical || 'generic',
  )
  const [loadingTemplates, setLoadingTemplates] = useState(false)
  const [templatesError, setTemplatesError] = useState<string | null>(null)
  const [templatesAttempt, setTemplatesAttempt] = useState(0)
  const [parsing, setParsing] = useState(false)
  const [parsingLane, setParsingLane] = useState<UploadLane | null>(null)
  const [stagedDraft, setStagedDraft] = useState<StagedOnboardingDraft | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)

  useEffect(() => {
    if (tenantVertical) setSelectedVertical(tenantVertical)
  }, [tenantVertical])

  useEffect(() => {
    let active = true
    setLoadingTemplates(true)
    setTemplatesError(null)
    onboardingKitsApi
      .list()
      .then((res) => {
        if (!active || !res.templates) return
        const all = res.templates
        // Tenant uploads: only the matching industry example (e.g. IT/software
        // sees Software & IT kit only — never every vertical's PDF).
        const next =
          lockToTenantVertical && tenantVertical
            ? all.filter((t) => t.vertical === tenantVertical)
            : all
        setTemplates(next.length ? next : all.filter((t) => t.vertical === 'generic').slice(0, 1))
      })
      .catch((err) => {
        console.warn('Failed loading onboarding kits:', err)
        if (active) {
          setTemplatesError(
            err instanceof Error ? err.message : 'The industry kit list could not be loaded.',
          )
        }
      })
      .finally(() => {
        if (active) setLoadingTemplates(false)
      })
    return () => {
      active = false
    }
  }, [templatesAttempt, lockToTenantVertical, tenantVertical])

  const currentTemplate =
    templates.find((t) => t.vertical === selectedVertical) || templates[0]

  const verticalLabel = tenantVertical
    ? getVertical(tenantVertical).label
    : currentTemplate?.title || 'Select Industry'

  const handleDownload = async (format: 'docx' | 'pdf') => {
    const slug = currentTemplate?.vertical || selectedVertical || tenantVertical || 'generic'
    try {
      await onboardingKitsApi.downloadKit(slug, format)
      toast.push(`Downloading ${currentTemplate?.title || slug} ${format.toUpperCase()} template…`)
    } catch (err: any) {
      toast.push(`Download failed: ${err?.message || 'try again'}`, 'error')
    }
  }

  const handleFileUpload = async (file: File, lane: UploadLane) => {
    setParsing(true)
    setParsingLane(lane)
    try {
      toast.push(
        lane === 'kit'
          ? `Staging kit ${file.name}…`
          : `Extracting bot details from ${file.name}…`,
      )
      let draft: StagedOnboardingDraft
      if (tenantId && tenantId !== 'draft_tenant') {
        draft = await onboardingKitsApi.stageTenant(tenantId, file, lane)
      } else {
        draft = await onboardingKitsApi.stageGlobal(file, lane)
      }
      setStagedDraft(draft)
      if (onStagedDraft) onStagedDraft(draft)

      if (draft.warning) {
        toast.push(draft.warning, 'error')
      }
      const mode = draft.extraction_mode === 'kit' ? 'kit parse' : 'general extraction'
      toast.push(
        `Ready to review (${mode}): ${draft.offerings?.length || 0} offerings, ${draft.faqs?.length || 0} FAQs, ${draft.intents?.length || 0} intents`,
      )
    } catch (err: any) {
      console.error('Document parsing failed:', err)
      toast.push(`Parsing failed: ${err.message || 'Check document format and try again'}`, 'error')
    } finally {
      setParsing(false)
      setParsingLane(null)
      if (anyFileRef.current) anyFileRef.current.value = ''
      if (kitFileRef.current) kitFileRef.current.value = ''
    }
  }

  const handleConfirmPublish = async (finalDraft: StagedOnboardingDraft) => {
    const tid = tenantId || finalDraft.tenant_id
    if (!tid || tid === 'draft_tenant') {
      if (onStagedDraft) onStagedDraft(finalDraft)
      setStagedDraft(null)
      toast.push('Full staged configuration saved to wizard!')
      return
    }

    setPublishing(true)
    try {
      const res = await onboardingKitsApi.publishTenant(tid, finalDraft)
      const intentsN = res.summary?.intents_count ?? finalDraft.intents?.length ?? 0
      toast.push(
        `Published! ${res.summary?.offerings_created ?? 0} offerings, ${res.summary?.kb_chunks_indexed ?? 0} KB chunks, ${intentsN} intents — Intents Editor updated.`,
      )
      setStagedDraft(null)
      if (onPublished) onPublished(res.summary)
    } catch (err: any) {
      toast.push(`Publishing failed: ${err.message || 'Server error'}`, 'error')
    } finally {
      setPublishing(false)
    }
  }

  const demoTemplate =
    (currentTemplate?.has_pdf ? currentTemplate : null) ||
    templates.find((t) => t.vertical === 'generic' && t.has_pdf) ||
    currentTemplate

  const handleDownloadDemoPdf = async () => {
    const slug = demoTemplate?.vertical || selectedVertical || tenantVertical || 'generic'
    try {
      await onboardingKitsApi.downloadKit(slug, 'pdf')
      toast.push(`Downloading tenant demo PDF (${demoTemplate?.title || slug})…`)
    } catch (err: any) {
      toast.push(`Download failed: ${err?.message || 'try again'}`, 'error')
    }
  }

  // First-login wizard: one upload + one demo PDF download (no Option A/B split).
  if (!ongoing && !kitOnly) {
    return (
      <>
        <div className="rounded-panel border border-acc/30 bg-accsoft/40 p-4 sm:p-5">
          <div className="flex flex-col items-start justify-between gap-4 lg:flex-row lg:items-center">
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accsoft text-acc">
                  <FolderUp className="h-4 w-4" />
                </span>
                <h3 className="text-sm font-semibold text-tx">Upload company document</h3>
                <span className="inline-flex rounded-full border border-acc/40 bg-accsoft px-2 py-0.5 text-2xs font-medium text-acc">
                  PDF / Word / Excel
                </span>
              </div>
              <p className="max-w-xl text-xs leading-relaxed text-txmuted">
                Download the tenant demo PDF for {verticalLabel}, fill in your details, then upload
                it here — or upload any brochure / company PDF you already have. We extract offerings,
                FAQs and knowledge for this setup.
              </p>
              {templatesError && (
                <Notice tone="bad" title="Demo PDF list failed to load" className="max-w-xl">
                  {templatesError}
                  <div className="mt-2">
                    <GhostButton
                      className="px-2.5 py-1.5 text-xs"
                      disabled={loadingTemplates}
                      onClick={() => setTemplatesAttempt((n) => n + 1)}
                    >
                      {loadingTemplates && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                      Retry
                    </GhostButton>
                  </div>
                </Notice>
              )}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <span className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-3 py-1.5 text-xs font-medium text-tx">
                  <span>{demoTemplate?.icon || currentTemplate?.icon || '🏢'}</span>
                  <span>{demoTemplate?.title || verticalLabel}</span>
                </span>
                <GhostButton
                  className="px-2.5 py-1.5 text-xs"
                  onClick={handleDownloadDemoPdf}
                  disabled={loadingTemplates && !demoTemplate}
                >
                  <Download className="h-3.5 w-3.5 text-acc" />
                  Download tenant demo PDF
                </GhostButton>
              </div>
            </div>

            <div className="flex flex-col items-center justify-center rounded-panel border border-dashed border-acc/40 bg-card p-4 text-center sm:min-w-[240px]">
              <input
                ref={anyFileRef}
                type="file"
                accept=".docx,.pdf,.doc,.xlsx,.csv,.txt,.md"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) handleFileUpload(f, 'any')
                }}
              />
              <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-accsoft text-acc">
                {parsing ? <Loader2 className="h-5 w-5 animate-spin" /> : <FolderUp className="h-5 w-5" />}
              </div>
              <p className="text-xs font-medium text-tx">
                {parsing ? 'Extracting…' : 'Upload filled demo or your PDF'}
              </p>
              <PrimaryButton
                className="mt-2 px-2.5 py-1.5 text-xs"
                disabled={parsing}
                onClick={() => anyFileRef.current?.click()}
              >
                {parsing && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Upload &amp; stage
              </PrimaryButton>
            </div>
          </div>
        </div>

        {stagedDraft && (
          <OnboardingReviewModal
            draft={stagedDraft}
            onClose={() => setStagedDraft(null)}
            onConfirm={handleConfirmPublish}
            publishing={publishing}
          />
        )}
      </>
    )
  }

  return (
    <>
      <div className="space-y-4">
        {/* Any document — primary path after onboarding */}
        {!kitOnly && (
        <div className="rounded-panel border border-acc/35 bg-accsoft/50 p-4 sm:p-5">
            <div className="flex flex-col items-start justify-between gap-4 lg:flex-row lg:items-center">
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accsoft text-acc">
                    <Files className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-semibold text-tx">
                    Upload a new or revised PDF / document
                  </h3>
                  <span className="inline-flex rounded-full border border-acc/40 bg-accsoft px-2 py-0.5 text-2xs font-medium text-acc">
                    Add or update after onboarding
                  </span>
                </div>
                <p className="max-w-xl text-xs leading-relaxed text-txmuted">
                  Upload another brochure, price list, FAQ sheet, or company document anytime. If a
                  document changes, re-upload the revised file with the same filename. We extract its
                  latest offerings, FAQs and knowledge, then let you review everything before publishing.
                </p>
                <div className="max-w-xl rounded-lg border border-line bg-card/80 px-3 py-2 text-2xs leading-relaxed text-txmuted">
                  <strong className="font-semibold text-tx">How re-uploads work:</strong>{' '}
                  matching offerings are updated, new items are added, and FAQ/knowledge extracted
                  from the same filename is refreshed. FAQ/knowledge from other files stays in place.
                </div>
              </div>
              <div className="flex flex-col items-center justify-center rounded-panel border border-dashed border-acc/45 bg-card p-4 text-center sm:min-w-[240px]">
                <input
                  ref={anyFileRef}
                  type="file"
                  accept=".docx,.pdf,.doc,.xlsx,.csv,.txt,.md"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) handleFileUpload(f, 'any')
                  }}
                />
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-accsoft text-acc">
                  {parsing && parsingLane === 'any' ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <FolderUp className="h-5 w-5" />
                  )}
                </div>
                <p className="text-xs font-medium text-tx">
                  {parsing && parsingLane === 'any' ? 'Extracting…' : 'New or revised PDF / Word / Excel'}
                </p>
                <PrimaryButton
                  className="mt-2 px-2.5 py-1.5 text-xs"
                  disabled={parsing}
                  onClick={() => anyFileRef.current?.click()}
                >
                  {parsing && parsingLane === 'any' && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  Upload / re-upload &amp; review
                </PrimaryButton>
              </div>
            </div>
        </div>
        )}

        {/* Pre-defined formatted industry kit (Knowledge / kitOnly) */}
        <div className="rounded-panel border border-line bg-card p-4 sm:p-5">
            <div className="flex flex-col items-start justify-between gap-4 lg:flex-row lg:items-center">
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accsoft text-acc">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <h3 className="text-sm font-semibold text-tx">
                    {kitOnly ? 'Pre-defined formatted PDF / Word kit' : 'Or use a filled industry kit'}
                  </h3>
                  <span className="inline-flex rounded-full border border-acc/40 bg-accsoft px-2 py-0.5 text-2xs font-medium text-acc">
                    Structured sections
                  </span>
                </div>
                <p className="max-w-xl text-xs leading-relaxed text-txmuted">
                  {lockToTenantVertical ? (
                    <>
                      Download the {verticalLabel} example kit for this tenant, fill the{' '}
                      <code className="text-2xs">[SECTION: …]</code> headers (Brand, WhatsApp,
                      Catalog, FAQs, Bot Persona), then upload it here.
                    </>
                  ) : (
                    <>
                      Download a template, keep <code className="text-2xs">[SECTION: …]</code> headers
                      (Brand, WhatsApp, Catalog, FAQs, Bot Persona). Incomplete kits fall back to
                      general extraction with a warning.
                    </>
                  )}
                </p>

                {templatesError && (
                  <Notice tone="bad" title="Industry kits failed to load" className="max-w-xl">
                    {templatesError}
                    <div className="mt-2">
                      <GhostButton
                        className="px-2.5 py-1.5 text-xs"
                        disabled={loadingTemplates}
                        onClick={() => setTemplatesAttempt((n) => n + 1)}
                      >
                        {loadingTemplates && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        Retry
                      </GhostButton>
                    </div>
                  </Notice>
                )}

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {lockToTenantVertical ? (
                    <span className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-3 py-1.5 text-xs font-medium text-tx">
                      <span>{currentTemplate?.icon || '🏢'}</span>
                      <span>{currentTemplate?.title || verticalLabel}</span>
                      <span className="text-txmuted">example only</span>
                    </span>
                  ) : (
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowDropdown(!showDropdown)}
                        disabled={loadingTemplates}
                        className="flex items-center gap-2 rounded-lg border border-line bg-card px-3 py-1.5 text-xs font-medium text-tx transition hover:border-acc"
                      >
                        <span>{currentTemplate?.icon || '🏢'}</span>
                        <span>{currentTemplate?.title || 'Select Industry'}</span>
                        <ChevronDown className="h-3 w-3 text-txmuted" />
                      </button>
                      {showDropdown && (
                        <div className="absolute left-0 top-full z-30 mt-1 w-64 rounded-lg border border-line bg-card p-1 shadow-xl">
                          {templates.map((tpl) => (
                            <button
                              key={tpl.vertical}
                              type="button"
                              onClick={() => {
                                setSelectedVertical(tpl.vertical)
                                setShowDropdown(false)
                              }}
                              className={`flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-xs transition ${
                                selectedVertical === tpl.vertical
                                  ? 'bg-accsoft font-medium text-acc'
                                  : 'text-tx hover:bg-paper'
                              }`}
                            >
                              <span>{tpl.icon}</span>
                              <span className="truncate">{tpl.title}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {currentTemplate?.has_docx !== false && (
                    <GhostButton
                      className="px-2.5 py-1.5 text-xs"
                      onClick={() => handleDownload('docx')}
                      disabled={!currentTemplate && loadingTemplates}
                    >
                      <Download className="h-3.5 w-3.5 text-acc" />
                      Word (.docx)
                    </GhostButton>
                  )}
                  {currentTemplate?.has_pdf !== false && (
                    <GhostButton
                      className="px-2.5 py-1.5 text-xs"
                      onClick={() => handleDownload('pdf')}
                      disabled={!currentTemplate && loadingTemplates}
                    >
                      <FileText className="h-3.5 w-3.5 text-badink" />
                      PDF example
                    </GhostButton>
                  )}
                </div>
              </div>

              <div className="flex flex-col items-center justify-center rounded-panel border border-dashed border-acc/40 bg-accsoft/40 p-4 text-center sm:min-w-[240px]">
                <input
                  ref={kitFileRef}
                  type="file"
                  accept=".docx,.pdf,.doc"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) handleFileUpload(f, 'kit')
                  }}
                />
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-accsoft text-acc">
                  {parsing && parsingLane === 'kit' ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <FolderUp className="h-5 w-5" />
                  )}
                </div>
                <p className="text-xs font-medium text-tx">
                  {parsing && parsingLane === 'kit' ? 'Parsing kit…' : 'Upload filled kit'}
                </p>
                <p className="mt-0.5 text-[10px] text-txmuted">Requires all 5 core sections</p>
                <PrimaryButton
                  className="mt-2 px-2.5 py-1.5 text-xs"
                  disabled={parsing}
                  onClick={() => kitFileRef.current?.click()}
                >
                  {parsing && parsingLane === 'kit' && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  Upload kit &amp; stage
                </PrimaryButton>
              </div>
            </div>
        </div>
      </div>

      {stagedDraft && (
        <OnboardingReviewModal
          draft={stagedDraft}
          onClose={() => setStagedDraft(null)}
          onConfirm={handleConfirmPublish}
          publishing={publishing}
        />
      )}
    </>
  )
}
