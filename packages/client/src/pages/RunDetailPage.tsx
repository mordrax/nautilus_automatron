import { useState, useCallback } from 'react'
import type * as echarts from 'echarts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import { PnlDistributionChart } from '@/components/chart/PnlDistributionChart'
import { PnlHoldTimeChart } from '@/components/chart/PnlHoldTimeChart'
import { PnlOverTimeChart } from '@/components/chart/PnlOverTimeChart'
import { EquityCurveChart } from '@/components/chart/EquityCurveChart'
import { TradesByMonthChart } from '@/components/chart/TradesByMonthChart'
import { TradeTable } from '@/components/trades/TradeTable'
import { TradeNavigator } from '@/components/trades/TradeNavigator'
import { CategorisationTable } from '@/components/trades/CategorisationTable'
import { useRunDetail, useTrades, useBars, useEquity } from '@/hooks/use-run-detail'
import { useTradeNavigation } from '@/hooks/use-trades'
import { useHotkeys } from '@/hooks/use-hotkeys'
import { useCategorisation } from '@/hooks/use-categorisation'
import { useIndicators } from '@/hooks/use-indicators'
import type { IndicatorMeta } from '@/types/api'

type IndicatorTogglesProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
}

const IndicatorToggles = ({ indicators, enabledIds, onToggle }: IndicatorTogglesProps) => {
  const overlays = indicators.filter(i => i.display === 'overlay')
  const panels = indicators.filter(i => i.display === 'panel')

  const renderGroup = (label: string, items: readonly IndicatorMeta[]) =>
    items.length > 0 && (
      <div>
        <h4 className="font-semibold mb-2 text-muted-foreground">{label}</h4>
        <div className="space-y-1">
          {items.map(ind => (
            <label key={ind.id} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabledIds.has(ind.id)}
                onChange={() => onToggle(ind.id)}
                className="rounded"
              />
              <span>{ind.label}</span>
            </label>
          ))}
        </div>
      </div>
    )

  return (
    <div className="space-y-4 text-sm">
      {renderGroup('Overlays', overlays)}
      {renderGroup('Panels', panels)}
    </div>
  )
}

type RunDetailPageProps = {
  readonly runId: string
}

export const RunDetailPage = ({ runId }: RunDetailPageProps) => {
  const { data: runDetail } = useRunDetail(runId)
  const { data: trades } = useTrades(runId)
  const barType = runDetail?.bar_types[0] ?? ''
  const { data: ohlc } = useBars(runId, barType)
  const { data: equity } = useEquity(runId)

  const [chartInstance, setChartInstance] = useState<echarts.ECharts | null>(null)

  const onChartReady = useCallback((chart: echarts.ECharts) => {
    setChartInstance(chart)
  }, [])

  const { currentIndex, currentTrade, navigateTrade, selectTrade } = useTradeNavigation(
    trades ?? [],
    ohlc,
    chartInstance,
  )

  const { categories, assignTrade, updateDescription } = useCategorisation()

  useHotkeys({
    onPrevTrade: useCallback(() => navigateTrade(-1), [navigateTrade]),
    onNextTrade: useCallback(() => navigateTrade(1), [navigateTrade]),
    onPrevTradeFast: useCallback(() => navigateTrade(-50), [navigateTrade]),
    onNextTradeFast: useCallback(() => navigateTrade(50), [navigateTrade]),
    onCategoryAssign: useCallback(
      (categoryId: number) => {
        if (currentTrade) assignTrade(categoryId, currentTrade.relative_id)
      },
      [currentTrade, assignTrade],
    ),
  })

  const { available, data: indicatorData, enabledIds, toggle } = useIndicators(barType)

  if (!runDetail) return <div className="text-muted-foreground">Loading...</div>

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">Run {runId.slice(0, 8)}...</h2>
        <Badge variant="secondary">{runDetail.total_positions} positions</Badge>
        <Badge variant="secondary">{runDetail.total_fills} fills</Badge>
        {runDetail.bar_types.map((bt) => (
          <Badge key={bt} variant="outline">{bt}</Badge>
        ))}
      </div>

      {/* Trade Navigator */}
      <TradeNavigator
        trade={currentTrade}
        totalTrades={trades?.length ?? 0}
        currentIndex={currentIndex}
        onPrev={() => navigateTrade(-1)}
        onNext={() => navigateTrade(1)}
      />

      {/* Chart + Indicator Panel */}
      <div className="flex gap-4">
        <Card className="flex-1">
          <CardContent className="p-0">
            {ohlc && trades ? (
              <CandlestickChart
                ohlc={ohlc}
                trades={trades}
                indicators={indicatorData}
                currentTradeIndex={currentIndex}
                onSelectTrade={selectTrade}
                onChartReady={onChartReady}
              />
            ) : (
              <div className="h-[600px] flex items-center justify-center text-muted-foreground">
                Loading chart data...
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="w-52 shrink-0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Indicators</CardTitle>
          </CardHeader>
          <CardContent>
            <IndicatorToggles
              indicators={available}
              enabledIds={enabledIds}
              onToggle={toggle}
            />
          </CardContent>
        </Card>
      </div>

      {/* Hotkey hint */}
      <p className="text-xs text-muted-foreground">
        Enable CapsLock, then use Arrow Left/Right to navigate trades (Shift+Arrow to skip 50)
      </p>

      {/* Trade Analysis Tabs */}
      <Tabs defaultValue="trades">
        <TabsList>
          <TabsTrigger value="trades">Trades</TabsTrigger>
          <TabsTrigger value="chart-analysis">Chart Analysis</TabsTrigger>
          <TabsTrigger value="categorisation">Categorisation</TabsTrigger>
          <TabsTrigger value="trades-by-month">Trades by Month</TabsTrigger>
        </TabsList>

        <TabsContent value="trades" className="min-h-[400px]">
          <Card>
            <CardHeader>
              <CardTitle>Trades ({trades?.length ?? 0})</CardTitle>
            </CardHeader>
            <CardContent>
              {trades ? (
                <TradeTable
                  trades={trades}
                  selectedIndex={currentIndex}
                  onSelectTrade={selectTrade}
                />
              ) : (
                <div className="text-muted-foreground">Loading trades...</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="chart-analysis" className="min-h-[400px]">
          {trades && trades.length > 0 ? (
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardContent className="p-2">
                  <div className="h-[400px]">
                    <PnlDistributionChart trades={trades} />
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-2">
                  <div className="h-[400px]">
                    <PnlHoldTimeChart trades={trades} onSelectTrade={selectTrade} />
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-2">
                  <div className="h-[400px]">
                    <PnlOverTimeChart trades={trades} onSelectTrade={selectTrade} />
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-2">
                  <div className="h-[400px]">
                    {equity ? (
                      <EquityCurveChart equity={equity} />
                    ) : (
                      <div className="flex items-center justify-center h-full text-muted-foreground">
                        Loading equity data...
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[400px] text-muted-foreground">
              Loading trade data...
            </div>
          )}
        </TabsContent>

        <TabsContent value="categorisation" className="min-h-[400px]">
          <Card>
            <CardHeader>
              <CardTitle>Trade Categorisation</CardTitle>
            </CardHeader>
            <CardContent>
              <CategorisationTable
                categories={categories}
                onUpdateDescription={updateDescription}
              />
              <p className="text-xs text-muted-foreground mt-4">
                CapsLock + 1-7 to assign current trade to a category. Double-click a description to edit.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trades-by-month" className="min-h-[400px]">
          {trades && trades.length > 0 ? (
            <Card>
              <CardContent className="p-2">
                <div className="h-[500px]">
                  <TradesByMonthChart trades={trades} />
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-[400px] text-muted-foreground">
              Loading trade data...
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
