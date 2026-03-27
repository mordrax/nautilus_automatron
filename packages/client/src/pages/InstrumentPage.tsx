import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import { useCatalogBars } from '@/hooks/use-catalog-bars'

type InstrumentPageProps = {
  readonly barType: string
}

export const InstrumentPage = ({ barType }: InstrumentPageProps) => {
  const decodedBarType = decodeURIComponent(barType)
  const { data: ohlc, isLoading, error } = useCatalogBars(decodedBarType)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">{decodedBarType}</h2>
        {ohlc && <Badge variant="secondary">{ohlc.datetime.length.toLocaleString()} bars</Badge>}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading && (
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              Loading chart data...
            </div>
          )}
          {error && (
            <div className="h-[600px] flex items-center justify-center text-destructive">
              Error loading bar data
            </div>
          )}
          {ohlc && <CandlestickChart ohlc={ohlc} />}
        </CardContent>
      </Card>
    </div>
  )
}
