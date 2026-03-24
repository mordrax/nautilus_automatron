import { useLocation } from 'wouter'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { RunSummary } from '@/types/api'

type RunListProps = {
  readonly runs: readonly RunSummary[]
}

export const RunList = ({ runs }: RunListProps) => {
  const [, setLocation] = useLocation()

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run ID</TableHead>
          <TableHead>Trader</TableHead>
          <TableHead>Strategy</TableHead>
          <TableHead className="text-right">Positions</TableHead>
          <TableHead className="text-right">Fills</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow
            key={run.run_id}
            className="cursor-pointer hover:bg-accent"
            onClick={() => setLocation(`/runs/${run.run_id}`)}
          >
            <TableCell className="font-mono text-xs">
              {run.run_id.slice(0, 8)}...
            </TableCell>
            <TableCell>{run.trader_id}</TableCell>
            <TableCell>
              <Badge variant="secondary">{run.strategy}</Badge>
            </TableCell>
            <TableCell className="text-right">{run.total_positions}</TableCell>
            <TableCell className="text-right">{run.total_fills}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
