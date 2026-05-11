import { Copy } from 'lucide-react'
import type { CatalogEntry } from '@/types/api'

type Props = {
  readonly barType: string
  readonly entry: CatalogEntry | undefined
}

const fmtDate = (iso: string): string => iso.slice(0, 10)
const fmtCount = (n: number): string => n.toLocaleString()

const onCopyPath = (path: string) => {
  navigator.clipboard?.writeText(path).catch(() => {
    /* clipboard may be unavailable in insecure contexts; ignore */
  })
}

export const CatalogTooltipContent = ({ barType, entry }: Props) => {
  if (!entry) {
    return (
      <div className="space-y-1">
        <div className="font-semibold">Not in catalog</div>
        <div className="font-mono text-[10px] opacity-80">{barType}</div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
      <span className="opacity-70">Symbol</span>
      <span className="font-mono">{entry.instrument}</span>

      {entry.venue && (
        <>
          <span className="opacity-70">Venue</span>
          <span className="font-mono">{entry.venue}</span>
        </>
      )}

      <span className="opacity-70">Timeframe</span>
      <span className="font-mono">{entry.timeframe}</span>

      <span className="opacity-70">Range</span>
      <span className="font-mono">
        {fmtDate(entry.start_date)} → {fmtDate(entry.end_date)}
      </span>

      <span className="opacity-70">Bars</span>
      <span className="font-mono">{fmtCount(entry.bar_count)}</span>

      <span className="opacity-70">Path</span>
      <span className="font-mono break-all flex items-center gap-1.5">
        <span>{entry.path}</span>
        <button
          type="button"
          aria-label="Copy path"
          onClick={(e) => {
            e.stopPropagation()
            onCopyPath(entry.path)
          }}
          className="opacity-70 hover:opacity-100 shrink-0"
        >
          <Copy className="size-3" />
        </button>
        <span className="opacity-60 shrink-0">({entry.file_count} {entry.file_count === 1 ? 'file' : 'files'})</span>
      </span>
    </div>
  )
}
