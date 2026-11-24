import { useState } from 'react'
import {
  Check,
  HelpCircle,
  Lightbulb,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  X,
} from 'lucide-react'
import { useAsync } from '@/lib/hooks'
import { knowledgeGapsApi, type KnowledgeGap } from '@/lib/uploads'
import { formatDate } from '@/lib/format'
import { cn } from '@/lib/cn'
import {
  EmptyState,
  ErrorBanner,
  FieldInput,
  FieldTextarea,
  GhostButton,
  NeedRow,
  Panel,
  Pill,
  PrimaryButton,
} from '@/components/remake/ui'
import { LoadingBlock } from '@/components/ui/feedback'
import { PageHeader } from '@/components/layout/page-header'
import { useToast } from '@/components/ui/toast'
import { Modal } from '@/components/ui/modal'

/**
 * WhatsApp → Settings: customer knowledge gaps and unanswered queries.
 * Moved here from the uploads / website-crawler file library.
 */
export function SettingsPanel({ tenantId }: { tenantId: string }) {
  const toast = useToast()

  const [showResolvedGaps, setShowResolvedGaps] = useState(false)
  const [gapModalItem, setGapModalItem] = useState<KnowledgeGap | null>(null)
  const [faqQuestion, setFaqQuestion] = useState('')
  const [faqAnswer, setFaqAnswer] = useState('')
  const [creatingFaq, setCreatingFaq] = useState(false)
  const [resolvingId, setResolvingId] = useState<number | null>(null)

  const gapsState = useAsync(
    (signal) => knowledgeGapsApi.list(tenantId, showResolvedGaps, 50, signal),
    [tenantId, showResolvedGaps],
  )

  const unresolvedGaps = !showResolvedGaps
    ? (gapsState.data?.gaps ?? []).filter((g) => g.resolved === 0)
    : []

  const openFaqCreator = (gap: KnowledgeGap) => {
    setGapModalItem(gap)
    setFaqQuestion(gap.query)
    setFaqAnswer('')
  }

  const onSaveFaq = async () => {
    if (!gapModalItem || !faqAnswer.trim()) {
      toast.push('Please enter an answer for the FAQ.', 'error')
      return
    }
    setCreatingFaq(true)
    try {
      await knowledgeGapsApi.createFaq(tenantId, gapModalItem.id, faqQuestion, faqAnswer)
      toast.push('FAQ published & indexed! Gap resolved.')
      setGapModalItem(null)
      gapsState.reload()
    } catch (err) {
      toast.push((err as Error).message || 'Failed to create FAQ', 'error')
    } finally {
      setCreatingFaq(false)
    }
  }

  const onResolveGap = async (gap: KnowledgeGap) => {
    setResolvingId(gap.id)
    try {
      await knowledgeGapsApi.resolve(tenantId, gap.id)
      toast.push('Knowledge gap marked resolved.')
      gapsState.reload()
    } catch (err) {
      toast.push((err as Error).message || 'Failed to resolve gap', 'error')
    } finally {
      setResolvingId(null)
    }
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="Settings"
        description="Review customer knowledge gaps and unanswered questions, then turn them into live FAQ answers."
      />

      {unresolvedGaps.length > 0 && (
        <Panel title="Needs you" className="mb-6">
          <NeedRow icon={<HelpCircle className="h-4 w-4" />}>
            <strong>{unresolvedGaps.length}</strong> customer{' '}
            {unresolvedGaps.length === 1 ? 'question is' : 'questions are'} still unanswered —
            turn them into FAQs below.
          </NeedRow>
        </Panel>
      )}

      <Panel
        className="border-attline bg-attbg"
        title="Customer Knowledge Gaps & Unanswered Queries"
        action={
          <div className="flex items-center gap-2">
            <GhostButton
              className={cn(
                'px-2.5 py-1.5 text-xs',
                showResolvedGaps && 'border-transparent bg-accsoft text-acc hover:text-acc',
              )}
              onClick={() => setShowResolvedGaps(!showResolvedGaps)}
            >
              {showResolvedGaps ? 'Showing Resolved' : 'Showing Unresolved'}
            </GhostButton>
            <GhostButton className="px-2.5 py-1.5 text-xs" onClick={gapsState.reload}>
              <RefreshCw className={cn('h-3.5 w-3.5', gapsState.loading && 'animate-spin')} />
              Refresh
            </GhostButton>
          </div>
        }
      >
        <div className="space-y-4">
          <p className="text-xs leading-relaxed text-txmuted">
            Real customer questions that scored below bot confidence thresholds or triggered fallback
            replies. Review the top questions the bot failed to answer and 1-click turn them into
            live FAQ answers to train your AI.
          </p>

          {gapsState.data?.summary.top_queries && gapsState.data.summary.top_queries.length > 0 && (
            <div className="rounded-panel border border-attline bg-card p-3.5">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-attink">
                <Lightbulb className="h-4 w-4" />
                <span>Top High-Frequency Questions Asked by Customers</span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {gapsState.data.summary.top_queries.slice(0, 6).map((tq, idx) => (
                  <div
                    key={idx}
                    className="flex flex-col justify-between rounded-panel border border-line bg-paper p-2.5"
                  >
                    <div>
                      <div className="mb-1 flex items-center justify-between gap-1">
                        <Pill tone="warn">
                          Asked {tq.count} {tq.count === 1 ? 'time' : 'times'}
                        </Pill>
                        <span className="text-2xs text-txmuted">{formatDate(tq.last_asked)}</span>
                      </div>
                      <p className="line-clamp-2 text-xs font-medium text-tx" title={tq.query}>
                        "{tq.query}"
                      </p>
                    </div>
                    <div className="mt-2 flex justify-end border-t border-linesoft pt-2">
                      <PrimaryButton
                        className="px-2.5 py-1.5 text-xs"
                        onClick={() =>
                          openFaqCreator({
                            id: tq.sample_id,
                            tenant_id: tenantId,
                            wa_id: null,
                            query: tq.query,
                            reason: tq.reason,
                            confidence_score: tq.avg_score,
                            created_at: tq.last_asked,
                            resolved: 0,
                          })
                        }
                      >
                        <Plus className="h-3 w-3" />
                        1-Click FAQ
                      </PrimaryButton>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {gapsState.loading && !gapsState.data ? (
            <LoadingBlock label="Loading knowledge gaps..." />
          ) : gapsState.error ? (
            <ErrorBanner title="Could not load knowledge gaps" message={gapsState.error} />
          ) : !gapsState.data?.gaps.length ? (
            <EmptyState
              title={showResolvedGaps ? 'No resolved queries' : 'No unanswered queries detected'}
              description={
                showResolvedGaps
                  ? 'Resolved questions will appear here.'
                  : 'Great job! The AI bot has successfully answered incoming customer questions with high confidence.'
              }
            />
          ) : (
            <ul className="divide-y divide-linesoft overflow-hidden rounded-panel border border-line bg-card">
              {gapsState.data.gaps.map((gap) => (
                <li
                  key={gap.id}
                  className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-tx">"{gap.query}"</span>
                      {gap.reason === 'no_match' && <Pill tone="bad">No FAQ Match</Pill>}
                      {gap.reason === 'low_confidence' && (
                        <Pill tone="warn">
                          Low Confidence ({gap.confidence_score.toFixed(2)})
                        </Pill>
                      )}
                      {gap.reason === 'uncertain_fallback' && (
                        <Pill tone="ok">Uncertain Fallback</Pill>
                      )}
                      {gap.resolved === 1 && <Pill tone="ok">Resolved</Pill>}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-2xs text-txmuted">
                      <span>Asked: {formatDate(gap.created_at)}</span>
                      {gap.wa_id && <span>User: {gap.wa_id}</span>}
                      {gap.resolution_notes && (
                        <span className="italic text-txmuted">({gap.resolution_notes})</span>
                      )}
                    </div>
                  </div>
                  {gap.resolved === 0 && (
                    <div className="flex shrink-0 items-center gap-2">
                      <PrimaryButton
                        className="px-2.5 py-1.5 text-xs"
                        onClick={() => openFaqCreator(gap)}
                      >
                        <Plus className="h-3.5 w-3.5" />
                        1-Click FAQ
                      </PrimaryButton>
                      <GhostButton
                        className="px-2.5 py-1.5 text-xs"
                        disabled={resolvingId === gap.id}
                        onClick={() => void onResolveGap(gap)}
                      >
                        {resolvingId === gap.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Check className="h-3.5 w-3.5" />
                        )}
                        Dismiss
                      </GhostButton>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      {gapModalItem && (
        <Modal
          onClose={() => setGapModalItem(null)}
          className="w-full max-w-lg rounded-panel border border-line bg-card p-5 shadow-2xl"
        >
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-tx">
              <Sparkles className="h-4 w-4 text-acc" />
              <span>Turn Question into Knowledge Base FAQ</span>
            </div>
            <button
              type="button"
              onClick={() => setGapModalItem(null)}
              aria-label="Close"
              className="text-txmuted transition hover:text-tx"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-4 py-4">
            <FieldInput
              label="Customer Question"
              value={faqQuestion}
              onChange={(e) => setFaqQuestion(e.target.value)}
              placeholder="E.g., What is your return policy?"
            />

            <FieldTextarea
              label="Official FAQ Answer"
              rows={4}
              value={faqAnswer}
              onChange={(e) => setFaqAnswer(e.target.value)}
              placeholder="Enter the clear, direct answer the bot should provide to customers..."
              hint="This will be added to the tenant FAQ dataset and immediately indexed in FAISS vector search."
            />
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-line pt-3">
            <GhostButton onClick={() => setGapModalItem(null)} disabled={creatingFaq}>
              Cancel
            </GhostButton>
            <PrimaryButton disabled={creatingFaq} onClick={() => void onSaveFaq()}>
              {creatingFaq ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Save &amp; Index FAQ
            </PrimaryButton>
          </div>
        </Modal>
      )}
    </div>
  )
}
