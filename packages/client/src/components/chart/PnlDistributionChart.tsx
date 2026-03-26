import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { computePnlDistribution } from '@/lib/trade-analysis'
import type { Trade } from '@/types/api'

type PnlDistributionChartProps = {
  readonly trades: readonly Trade[]
}

const buildOption = (trades: readonly Trade[]): echarts.EChartsOption => {
  const bins = computePnlDistribution(trades, 40)

  return {
    animation: false,
    title: { text: 'Trade P/L Distribution', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const p = (params as readonly { readonly value: number; readonly name: string }[])[0]
        return `P/L Range: ${p.name}<br/>Trades: ${p.value}`
      },
    },
    xAxis: {
      type: 'category',
      data: bins.map(b => b.center.toFixed(2)),
      name: 'P/L',
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: 'Frequency',
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%' },
    ],
    grid: { left: '8%', right: '5%', bottom: '18%', top: '15%' },
    series: [
      {
        type: 'bar',
        data: bins.map(b => ({
          value: b.count,
          itemStyle: {
            color: b.isPositive ? CHART_COLORS.tradeWin : CHART_COLORS.tradeLoss,
          },
        })),
      },
    ],
  }
}

export const PnlDistributionChart = ({ trades }: PnlDistributionChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chart.setOption(buildOption(trades))

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
      data-testid="pnl-distribution-chart"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
