import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { formatDatetime } from '@/lib/trade-utils'
import type { EquityPoint } from '@/types/api'

type EquityCurveChartProps = {
  readonly equity: readonly EquityPoint[]
}

const buildOption = (equity: readonly EquityPoint[]): echarts.EChartsOption => {
  if (equity.length === 0) return {}

  const startingBalance = equity[0].equity
  const lastBalance = equity[equity.length - 1].equity
  const lineColor = lastBalance >= startingBalance ? CHART_COLORS.tradeWin : CHART_COLORS.tradeLoss

  const data = equity.map(p => [p.timestamp, p.equity])

  return {
    animation: false,
    title: { text: 'Equity Curve', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = (params as readonly { readonly value: readonly [string, number] }[])[0]
        return `Date: ${formatDatetime(p.value[0])}<br/>Balance: ${Math.floor(p.value[1]).toLocaleString()}`
      },
    },
    xAxis: { type: 'time', name: 'Date' },
    yAxis: {
      type: 'value',
      name: 'Balance',
      min: 'dataMin',
      max: 'dataMax',
      axisLabel: { formatter: (v: number) => v.toFixed(0) },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%' },
    ],
    grid: { left: '10%', right: '5%', bottom: '18%', top: '15%' },
    series: [
      {
        type: 'line',
        data,
        symbolSize: 1,
        showSymbol: false,
        lineStyle: { color: lineColor },
        areaStyle: { color: lineColor, opacity: 0.1 },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#888' },
          data: [{ yAxis: startingBalance, label: { formatter: 'Start' } }],
        },
      },
    ],
  }
}

export const EquityCurveChart = ({ equity }: EquityCurveChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartDivRef.current || equity.length === 0) return

    const chart = echarts.init(chartDivRef.current)
    chart.setOption(buildOption(equity))

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
    }
  }, [equity])

  return (
    <div
      ref={chartDivRef}
      data-testid="equity-curve-chart"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
