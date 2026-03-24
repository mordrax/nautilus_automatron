import { useState, useCallback } from 'react'
import type * as echarts from 'echarts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import { TradeTable } from '@/components/trades/TradeTable'
import { TradeNavigator } from '@/components/trades/TradeNavigator'
import { useRunDetail, useTrades, useBars } from '@/hooks/use-run-detail'
import { useTradeNavigation } from '@/hooks/use-trades'
import { useHotkeys } from '@/hooks/use-hotkeys'

type RunDetailPageProps = {
  readonly runId: string
}

export const RunDetailPage = ({ runId }: RunDetailPageProps) => {
  const { data: runDetail } = useRunDetail(runId)
  const { data: trades } = useTrades(runId)
  const barType = runDetail?.bar_types[0] ?? ''
  const { data: ohlc } = useBars(runId, barType)

  const [chartInstance, setChartInstance] = useState<echarts.ECharts | null>(null)

  const onChartReady = useCallback((chart: echarts.ECharts) => {
    setChartInstance(chart)
  }, [])

  const { currentIndex, currentTrade, navigateTrade, selectTrade } = useTradeNavigation(
    trades ?? [],
    ohlc,
    chartInstance,
  )

  useHotkeys({
    onPrevTrade: useCallback(() => navigateTrade(-1), [navigateTrade]),
    onNextTrade: useCallback(() => navigateTrade(1), [navigateTrade]),
    onPrevTradeFast: useCallback(() => navigateTrade(-50), [navigateTrade]),
    onNextTradeFast: useCallback(() => navigateTrade(50), [navigateTrade]),
  })

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

      {/* Chart */}
      <Card>
        <CardContent className="p-0">
          {ohlc && trades ? (
            <CandlestickChart
              ohlc={ohlc}
              trades={trades}
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

      {/* Hotkey hint */}
      <p className="text-xs text-muted-foreground">
        Enable CapsLock, then use Arrow Left/Right to navigate trades (Shift+Arrow to skip 50)
      </p>

      {/* Trade Table */}
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
    </div>
  )
}
