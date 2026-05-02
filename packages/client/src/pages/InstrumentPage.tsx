import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import { IndicatorToggles } from '@/components/chart/IndicatorToggles'
import { KeyLevelsPanel } from '@/components/chart/KeyLevelsPanel'
import { useCatalogBars } from '@/hooks/use-catalog-bars'
import { useIndicators } from '@/hooks/use-indicators'
import { useKeyLevels } from '@/hooks/use-key-levels'

type InstrumentPageProps = {
  readonly barType: string
}

export const InstrumentPage = ({ barType }: InstrumentPageProps) => {
  const decodedBarType = decodeURIComponent(barType)
  const { data: ohlc, isLoading, error } = useCatalogBars(decodedBarType)
  const { available, data: indicatorData, enabledIds, toggle, getColor, setColor } = useIndicators(decodedBarType)

  const [selectedDetectors, setSelectedDetectors] = useState<readonly string[]>([])
  const { data: keyLevels } = useKeyLevels(decodedBarType, selectedDetectors)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">{decodedBarType}</h2>
        {ohlc && <Badge variant="secondary">{ohlc.datetime.length.toLocaleString()} bars</Badge>}
      </div>

      <div className="flex gap-4">
        <Card className="flex-1">
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
            {ohlc && (
              <CandlestickChart
                ohlc={ohlc}
                indicators={indicatorData}
                keyLevels={keyLevels ?? []}
                getIndicatorColor={getColor}
              />
            )}
          </CardContent>
        </Card>

        <Card className="w-52 shrink-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Indicators</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <IndicatorToggles
              indicators={available}
              enabledIds={enabledIds}
              onToggle={toggle}
              getColor={getColor}
              onColorChange={setColor}
            />
            <KeyLevelsPanel
              selectedDetectors={selectedDetectors}
              onChange={setSelectedDetectors}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
