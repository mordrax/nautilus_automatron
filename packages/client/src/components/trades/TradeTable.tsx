import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { formatPnl, formatDatetime } from '@/lib/trade-utils'
import type { Trade } from '@/types/api'

type TradeTableProps = {
  readonly trades: readonly Trade[]
  readonly selectedIndex: number
  readonly onSelectTrade: (index: number) => void
}

export const TradeTable = ({ trades, selectedIndex, onSelectTrade }: TradeTableProps) => (
  <div className="max-h-[400px] overflow-auto">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">#</TableHead>
          <TableHead>Direction</TableHead>
          <TableHead>Entry Time</TableHead>
          <TableHead>Exit Time</TableHead>
          <TableHead className="text-right">Entry Price</TableHead>
          <TableHead className="text-right">Exit Price</TableHead>
          <TableHead className="text-right">P&L</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {trades.map((trade, idx) => (
          <TableRow
            key={trade.position_id}
            className={cn(
              'cursor-pointer',
              idx === selectedIndex && 'bg-accent',
            )}
            onClick={() => onSelectTrade(idx)}
          >
            <TableCell className="font-mono text-xs">{trade.relative_id}</TableCell>
            <TableCell>{trade.direction}</TableCell>
            <TableCell className="text-xs">{formatDatetime(trade.entry_datetime)}</TableCell>
            <TableCell className="text-xs">{formatDatetime(trade.exit_datetime)}</TableCell>
            <TableCell className="text-right font-mono">{trade.entry_price.toFixed(5)}</TableCell>
            <TableCell className="text-right font-mono">{trade.exit_price.toFixed(5)}</TableCell>
            <TableCell
              className={cn(
                'text-right font-mono font-semibold',
                trade.pnl >= 0 ? 'text-green-600' : 'text-red-600',
              )}
            >
              {formatPnl(trade.pnl)} {trade.currency}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </div>
)
