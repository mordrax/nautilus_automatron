import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { computeHoldTimeHours } from '@/lib/trade-analysis'
import { formatPnl } from '@/lib/trade-utils'
import type { Trade } from '@/types/api'

type PnlHoldTimeChartProps = {
  readonly trades: readonly Trade[]
  readonly onSelectTrade: (index: number) => void
}

const buildOption = (trades: readonly Trade[]): echarts.EChartsOption => {
  const data = trades.map((t, i) => ({
    value: [computeHoldTimeHours(t), t.pnl, i],
    itemStyle: { color: t.pnl >= 0 ? CHART_COLORS.tradeWin : CHART_COLORS.tradeLoss },
  }))

  return {
    animation: false,
    title: { text: 'P/L vs Hold Time', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { readonly value: readonly number[] }
        const trade = trades[p.value[2]]
        return `Trade #${trade.relative_id}<br/>Hold Time: ${p.value[0].toFixed(2)}h<br/>P/L: ${formatPnl(p.value[1])}`
      },
    },
    xAxis: { type: 'value', name: 'Hold Time (hours)' },
    yAxis: { type: 'value', name: 'P/L' },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%' },
    ],
    grid: { left: '10%', right: '5%', bottom: '18%', top: '15%' },
    series: [{ type: 'scatter', data, symbolSize: 8 }],
  }
}

export const PnlHoldTimeChart = ({ trades, onSelectTrade }: PnlHoldTimeChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)
  const selectTradeRef = useRef(onSelectTrade)

  useEffect(() => {
    selectTradeRef.current = onSelectTrade
  }, [onSelectTrade])

  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chart.setOption(buildOption(trades))

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    chart.on('click', 'series', (params: any) => {
      const tradeIndex = params.value?.[2]
      if (tradeIndex != null) selectTradeRef.current(tradeIndex)
    })

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
    }
  }, [trades])

  return (
    <div
      ref={chartDivRef}
      data-testid="pnl-hold-time-chart"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
