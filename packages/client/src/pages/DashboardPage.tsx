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

  return (
    <div className="px-2 py-4 space-y-8">
      <section>
        <h2 className="text-xl font-semibold mb-4 px-2">Instrument Data Catalog</h2>
        {catalogLoading && <div className="text-muted-foreground p-4">Loading catalog...</div>}
        {catalogError && <div className="text-destructive p-4">Error loading catalog</div>}
        {catalogData && catalogData.length > 0 && <CatalogTable entries={catalogData} />}
        {catalogData && catalogData.length === 0 && (
          <div className="text-muted-foreground p-4">No instrument data in catalog</div>
        )}
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4 px-2">
          Backtest Runs {runsData ? `(${runsData.total})` : ''}
        </h2>
        <div className="flex justify-end mb-4">
          <Button onClick={() => setLocation('/create')}>New Backtest</Button>
        </div>
        {runsLoading && <div className="text-muted-foreground p-4">Loading runs...</div>}
        {runsError && <div className="text-destructive p-4">Error loading runs</div>}
        {runsData && (
          <RunList
            runs={runsData.runs}
            onRerun={(runId) => rerunMutation.mutate(runId)}
            onDelete={(runId) => deleteMutation.mutate(runId)}
          />
        )}
      </section>
    </div>
  )
}
