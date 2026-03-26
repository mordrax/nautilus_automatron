import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { computeTradesByMonth } from '@/lib/trade-analysis'
import type { Trade } from '@/types/api'

type TradesByMonthChartProps = {
  readonly trades: readonly Trade[]
}

const buildOption = (trades: readonly Trade[]): echarts.EChartsOption => {
  const { months, counts } = computeTradesByMonth(trades)

  return {
    animation: false,
    title: { text: 'Trades by Month', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const p = (params as readonly { readonly value: number; readonly name: string }[])[0]
        return `${p.name}<br/>Trades: ${p.value}`
      },
    },
    xAxis: {
      type: 'category',
      data: months as string[],
      name: 'Month',
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: 'Trades',
      minInterval: 1,
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%' },
    ],
    grid: { left: '8%', right: '5%', bottom: '18%', top: '15%' },
    series: [
      {
        type: 'bar',
        data: counts.map(c => ({
          value: c,
          itemStyle: { color: CHART_COLORS.tradeWin },
        })),
      },
    ],
  }
}

export const TradesByMonthChart = ({ trades }: TradesByMonthChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chart.setOption(buildOption(trades))

    // Expose chart instance for e2e test access
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(chartDivRef.current as any)._ec_instance = chart

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
      data-testid="trades-by-month-chart"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
