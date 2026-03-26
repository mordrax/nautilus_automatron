import { RunList } from '@/components/runs/RunList'
import { useRuns } from '@/hooks/use-runs'

export const RunsPage = () => {
  const { data, isLoading, error } = useRuns()

  if (isLoading) return <div className="text-muted-foreground p-4">Loading runs...</div>
  if (error) return <div className="text-destructive p-4">Error loading runs</div>
  if (!data) return null

  return (
    <div className="px-2 py-4">
      <h2 className="text-xl font-semibold mb-4 px-2">Backtest Runs ({data.total})</h2>
      <RunList runs={data.runs} />
    </div>
  )
}
