/** Parse ISO, ``YYYY-MM-DD HH:mm:ss``, or DB stamp ``DD-MM-YYYY HH:mm``. */
function parseDisplayDate(value: string): Date | null {
  const trimmed = value.trim()
  const dmy = /^(\d{2})-(\d{2})-(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/.exec(trimmed)
  if (dmy) {
    const [, dd, mm, yyyy, hh = '00', min = '00', ss = '00'] = dmy
    const date = new Date(
      Number(yyyy),
      Number(mm) - 1,
      Number(dd),
      Number(hh),
      Number(min),
      Number(ss),
    )
    return Number.isNaN(date.getTime()) ? null : date
  }
  const date = new Date(trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T'))
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDate(value?: string | null): string {
  if (!value) return '—'
  const date = parseDisplayDate(value)
  if (!date) return value
  return date.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(value?: string | null): string {
  if (!value) return '—'
  const date = parseDisplayDate(value)
  if (!date) return value
  const diff = Date.now() - date.getTime()
  const minutes = Math.round(diff / 60000)
  // Future / clock-skew timestamps used to all show "just now" because
  // negative minute diffs satisfied `minutes < 1`.
  if (minutes < -2) return formatDate(value)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return formatDate(value)
}

export function isTruthyFlag(value: unknown): boolean {
  return value === true || value === 1 || value === '1'
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return `${count} ${count === 1 ? singular : (plural ?? `${singular}s`)}`
}
