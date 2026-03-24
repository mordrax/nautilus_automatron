import { Button } from '@/components/ui/button'
import { formatPnl, formatDatetime } from '@/lib/trade-utils'
import { cn } from '@/lib/utils'
import type { Trade } from '@/types/api'

type TradeNavigatorProps = {
  readonly trade: Trade | null
  readonly totalTrades: number
  readonly currentIndex: number
  readonly onPrev: () => void
  readonly onNext: () => void
}

export const TradeNavigator = ({
  trade,
  totalTrades,
  currentIndex,
  onPrev,
  onNext,
}: TradeNavigatorProps) => {
  if (!trade) return null

  return (
    <div className="flex items-center gap-4 p-3 border rounded-md bg-card">
      <Button variant="outline" size="sm" onClick={onPrev}>
        ← Prev
      </Button>
      <div className="flex-1 text-sm">
        <span className="font-mono font-semibold">
          Trade #{trade.relative_id}
        </span>
        <span className="text-muted-foreground mx-2">|</span>
        <span>{trade.direction}</span>
        <span className="text-muted-foreground mx-2">|</span>
        <span className="text-xs">
          {formatDatetime(trade.entry_datetime)} → {formatDatetime(trade.exit_datetime)}
        </span>
        <span className="text-muted-foreground mx-2">|</span>
        <span
          className={cn(
            'font-mono font-semibold',
            trade.pnl >= 0 ? 'text-green-600' : 'text-red-600',
          )}
        >
          {formatPnl(trade.pnl)} {trade.currency}
        </span>
      </div>
      <span className="text-xs text-muted-foreground">
        {currentIndex + 1} / {totalTrades}
      </span>
      <Button variant="outline" size="sm" onClick={onNext}>
        Next →
      </Button>
    </div>
  )
}
