import { cn } from '@/lib/cn'

/** Horizontal bar chart — top questions / category counts. */
export function BarChart({
  items,
  className,
}: {
  items: { label: string; value: number }[]
  className?: string
}) {
  const max = Math.max(1, ...items.map((i) => i.value))
  if (!items.length) {
    return <p className="py-8 text-center text-sm text-txmuted">No data yet</p>
  }
  return (
    <ul className={cn('space-y-3', className)}>
      {items.map((item, idx) => {
        const pct = Math.round((item.value / max) * 100)
        return (
          <li key={`${item.label}-${idx}`} className="min-w-0">
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="truncate text-sm text-tx" title={item.label}>
                {item.label}
              </span>
              <span className="shrink-0 text-xs font-semibold tabular-nums text-txmuted">
                {item.value}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-md bg-linesoft">
              <div
                className="h-full rounded-md bg-acc transition-[width] duration-700 ease-out"
                style={{ width: `${pct}%`, animationDelay: `${idx * 40}ms` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** Donut chart for route / category breakdown. */
export function DonutChart({
  slices,
  centerLabel,
  centerValue,
  className,
}: {
  slices: { label: string; value: number; color: string }[]
  centerLabel?: string
  centerValue?: string | number
  className?: string
}) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1
  const size = 160
  const stroke = 22
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  let offset = 0

  if (!slices.length || slices.every((s) => !s.value)) {
    return (
      <div className={cn('flex flex-col items-center gap-4 sm:flex-row', className)}>
        <div className="flex h-40 w-40 items-center justify-center rounded-full bg-linesoft text-sm text-txmuted">
          No data
        </div>
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col items-center gap-5 sm:flex-row sm:items-start', className)}>
      <div className="relative shrink-0">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="rgb(var(--line-soft))"
            strokeWidth={stroke}
          />
          {slices.map((slice, i) => {
            if (!slice.value) return null
            const len = (slice.value / total) * c
            const el = (
              <circle
                key={i}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={slice.color}
                strokeWidth={stroke}
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
                className="transition-all duration-700"
              />
            )
            offset += len
            return el
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-bold tabular-nums text-tx">{centerValue ?? total}</span>
          {centerLabel ? <span className="mt-0.5 text-xs text-txmuted">{centerLabel}</span> : null}
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-2 self-center">
        {slices.map((slice) => (
          <li key={slice.label} className="flex items-center gap-2 text-sm">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: slice.color }}
            />
            <span className="min-w-0 flex-1 truncate text-txmuted">{slice.label}</span>
            <span className="tabular-nums font-medium text-tx">{slice.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Simple area / line spark for response-time trend. */
export function SparkArea({
  points,
  className,
  valueSuffix = 'ms',
}: {
  points: { label: string; value: number }[]
  className?: string
  valueSuffix?: string
}) {
  if (!points.length) {
    return <p className="py-8 text-center text-sm text-txmuted">No trend data yet</p>
  }
  const w = 420
  const h = 140
  const pad = 8
  const max = Math.max(1, ...points.map((p) => p.value))
  const min = Math.min(...points.map((p) => p.value), 0)
  const span = Math.max(1, max - min)
  const coords = points.map((p, i) => {
    const x = pad + (i / Math.max(1, points.length - 1)) * (w - pad * 2)
    const y = h - pad - ((p.value - min) / span) * (h - pad * 2)
    return { x, y, ...p }
  })
  const line = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ')
  const area = `${line} L${coords[coords.length - 1].x},${h - pad} L${coords[0].x},${h - pad} Z`
  const last = coords[coords.length - 1]

  return (
    <div className={cn('min-w-0', className)}>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-xs text-txmuted">Last {points.length} days</span>
        <span className="text-lg font-bold tabular-nums text-tx">
          {Math.round(last.value)}
          <span className="ml-1 text-xs font-medium text-txmuted">{valueSuffix}</span>
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-36 w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(var(--acc))" stopOpacity="0.28" />
            <stop offset="100%" stopColor="rgb(var(--acc))" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#sparkFill)" />
        <path
          d={line}
          fill="none"
          stroke="rgb(var(--acc))"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle cx={last.x} cy={last.y} r="4" fill="rgb(var(--acc))" />
      </svg>
      <div className="mt-1 flex justify-between text-xs text-txfaint">
        <span>{points[0]?.label}</span>
        <span>{points[points.length - 1]?.label}</span>
      </div>
    </div>
  )
}

/** Progress ring for solved / total ratios. */
export function ProgressRing({
  value,
  total,
  label,
  className,
}: {
  value: number
  total: number
  label: string
  className?: string
}) {
  const pct = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0
  const size = 88
  const stroke = 8
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const filled = (pct / 100) * c

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <svg width={size} height={size} className="-rotate-90 shrink-0">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgb(var(--line-soft))"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgb(var(--acc))"
          strokeWidth={stroke}
          strokeDasharray={`${filled} ${c - filled}`}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <div className="min-w-0">
        <p className="text-xl font-bold tabular-nums text-tx">{pct}%</p>
        <p className="text-sm text-txmuted">{label}</p>
        <p className="text-xs text-txfaint">
          {value} / {total}
        </p>
      </div>
    </div>
  )
}
