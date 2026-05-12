import { useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import { IndicatorInstanceSelector } from '@/components/chart/indicator-selector/IndicatorSelector'
import { ActiveIndicatorChip } from '@/components/chart/indicator-selector/ActiveIndicatorChip'
import { useCatalogBars } from '@/hooks/use-catalog-bars'
import { useIndicators } from '@/hooks/use-indicators'
import { useDetectors, useKeyLevels } from '@/hooks/use-key-levels'
import type { DetectorMeta } from '@/types/key-levels'

type DetectorSelectorProps = {
  readonly detectors: readonly DetectorMeta[]
  readonly selectedIds: readonly string[]
  readonly onToggle: (id: string) => void
}

const DetectorSelector = ({ detectors, selectedIds, onToggle }: DetectorSelectorProps) => {
  if (detectors.length === 0) return null
  const selectedSet = new Set(selectedIds)

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-1.5">Key Levels</p>
      <div className="flex flex-wrap gap-1.5">
        {selectedIds
          .map(id => detectors.find(d => d.id === id))
          .filter((d): d is DetectorMeta => d !== undefined)
          .map(det => (
            <ActiveIndicatorChip
              key={det.id}
              id={det.id}
              label={det.label}
              color={det.color}
              onRemove={onToggle}
            />
          ))}
        {detectors
          .filter(d => !selectedSet.has(d.id))
          .map(det => (
            <button
              key={det.id}
              type="button"
              onClick={() => onToggle(det.id)}
              className="inline-flex items-center gap-1.5 pl-1 pr-1.5 py-0.5 rounded-md border border-dashed border-border bg-background text-xs text-muted-foreground hover:text-foreground hover:border-solid cursor-pointer"
            >
              <span
                className="w-3 h-3 rounded-sm border border-border shrink-0"
                style={{ backgroundColor: det.color }}
              />
              <span className="whitespace-nowrap">{det.label}</span>
            </button>
          ))}
      </div>
    </div>
  )
}

type InstrumentPageProps = {
  readonly barType: string
}

export const InstrumentPage = ({ barType }: InstrumentPageProps) => {
  const decodedBarType = decodeURIComponent(barType)
  const { data: ohlc, isLoading, error } = useCatalogBars(decodedBarType)
  const { types, instances, data: indicatorData, addInstance, editInstance, removeInstance, getColor, setColor } = useIndicators(null, decodedBarType)

  const [selectedDetectors, setSelectedDetectors] = useState<readonly string[]>([])
  const { data: detectors = [] } = useDetectors()
  const { data: keyLevels } = useKeyLevels(decodedBarType, selectedDetectors)

  const toggleDetector = useCallback(
    (id: string) => setSelectedDetectors(prev =>
      prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id]
    ),
    [],
  )

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
            <IndicatorInstanceSelector
              types={types}
              instances={instances}
              getColor={getColor}
              onSetColor={setColor}
              onAdd={addInstance}
              onEdit={editInstance}
              onRemove={removeInstance}
            />
            <DetectorSelector
              detectors={detectors}
              selectedIds={selectedDetectors}
              onToggle={toggleDetector}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
