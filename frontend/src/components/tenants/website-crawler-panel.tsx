import { useMemo, useState } from 'react'
import { cn } from '@/lib/cn'
import { PageHeader } from '@/components/layout/page-header'
import { UploadsPanel } from '@/components/tenants/uploads-panel'
import { WebsiteKnowledgePanel } from '@/components/tenants/website-knowledge-panel'

type CrawlerTab = 'crawl' | 'upload' | 'files'

const TABS: { id: CrawlerTab; label: string }[] = [
  { id: 'crawl', label: 'Crawl' },
  { id: 'upload', label: 'Upload documents' },
  { id: 'files', label: 'Files (FAQ, KB, …)' },
]

/**
 * Merged knowledge hub: website crawl, document upload session, and the
 * FAQ/KB/brochure file library — one sidebar door for what used to be
 * Knowledge / Website knowledge / Files.
 */
export function WebsiteCrawlerPanel({
  tenantId,
  initialTab = 'crawl',
}: {
  tenantId: string
  initialTab?: CrawlerTab | 'uploads'
}) {
  const resolvedInitial: CrawlerTab =
    initialTab === 'uploads' || initialTab === 'files'
      ? 'files'
      : initialTab === 'upload'
        ? 'upload'
        : 'crawl'
  const [tab, setTab] = useState<CrawlerTab>(resolvedInitial)
  const active = useMemo(() => TABS.find((t) => t.id === tab) ?? TABS[0], [tab])

  return (
    <div className="min-w-0">
      <PageHeader
        title="Website crawler"
        description="Crawl the site, run a document upload session, or manage FAQ / knowledge-base / brochure files — then review and publish."
      />

      <div
        role="tablist"
        aria-label="Website crawler sections"
        className="mb-5 flex flex-wrap gap-1 border-b border-line"
      >
        {TABS.map((item) => {
          const selected = item.id === active.id
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setTab(item.id)}
              className={cn(
                '-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                selected
                  ? 'border-acc text-tx'
                  : 'border-transparent text-txmuted hover:text-tx',
              )}
            >
              {item.label}
            </button>
          )
        })}
      </div>

      <div role="tabpanel">
        {tab === 'crawl' && <WebsiteKnowledgePanel tenantId={tenantId} embedded />}
        {tab === 'upload' && (
          <UploadsPanel tenantId={tenantId} embedded section="kit" />
        )}
        {tab === 'files' && (
          <UploadsPanel tenantId={tenantId} embedded section="library" />
        )}
      </div>
    </div>
  )
}
