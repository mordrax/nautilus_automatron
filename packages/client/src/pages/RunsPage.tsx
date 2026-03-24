import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RunList } from '@/components/runs/RunList'
import { useRuns } from '@/hooks/use-runs'

export const RunsPage = () => {
  const { data, isLoading, error } = useRuns()

  if (isLoading) return <div className="text-muted-foreground">Loading runs...</div>
  if (error) return <div className="text-destructive">Error loading runs</div>
  if (!data) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backtest Runs ({data.total})</CardTitle>
      </CardHeader>
      <CardContent>
        <RunList runs={data.runs} />
      </CardContent>
    </Card>
  )
}
