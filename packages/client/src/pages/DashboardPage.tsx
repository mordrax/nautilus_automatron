import { useCallback } from 'react'
import { RunList } from '@/components/runs/RunList'
import { CatalogTable } from '@/components/catalog/CatalogTable'
import { useRuns } from '@/hooks/use-runs'
import { useCatalog } from '@/hooks/use-catalog'
import { useRerunBacktest, useDeleteBacktest } from '@/hooks/use-mutations'
import { useLocation } from 'wouter'
import { Button } from '@/components/ui/button'

export const DashboardPage = () => {
  const { data: runsData, isLoading: runsLoading, error: runsError } = useRuns()
  const { data: catalogData, isLoading: catalogLoading, error: catalogError } = useCatalog()
  const rerunMutation = useRerunBacktest()
  const deleteMutation = useDeleteBacktest()
  const [, setLocation] = useLocation()

  const handleViewInstrument = useCallback(
    (barType: string) => setLocation(`/instruments/${encodeURIComponent(barType)}`),
    [setLocation],
  )

  return (
    <div className="px-2 py-4 space-y-8">
      <section>
        {catalogLoading && <div className="text-muted-foreground p-4">Loading catalog...</div>}
        {catalogError && <div className="text-destructive p-4">Error loading catalog</div>}
        {catalogData && catalogData.length > 0 && (
          <CatalogTable
            entries={catalogData}
            title="Instrument Data Catalog"
            onViewInstrument={handleViewInstrument}
          />
        )}
        {catalogData && catalogData.length === 0 && (
          <div className="text-muted-foreground p-4">No instrument data in catalog</div>
        )}
      </section>

      <section>
        <div className="flex justify-end mb-4 px-2">
          <Button onClick={() => setLocation('/create')}>New Backtest</Button>
        </div>
        {runsLoading && <div className="text-muted-foreground p-4">Loading runs...</div>}
        {runsError && <div className="text-destructive p-4">Error loading runs</div>}
        {runsData && (
          <RunList
            runs={runsData.runs}
            title={`Backtest Runs (${runsData.total})`}
            onRerun={(runId) => rerunMutation.mutate(runId)}
            onDelete={(runId) => deleteMutation.mutate(runId)}
          />
        )}
      </section>
    </div>
  )
}
