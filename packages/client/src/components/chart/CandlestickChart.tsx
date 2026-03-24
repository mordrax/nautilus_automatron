import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { buildTradeMarkLines, formatTradeTooltip, formatDatetime } from '@/lib/trade-utils'
import type { OhlcData, Trade } from '@/types/api'

type CandlestickChartProps = {
  readonly ohlc: OhlcData
  readonly trades: readonly Trade[]
  readonly onChartReady?: (chart: echarts.ECharts) => void
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const buildOption = (ohlc: OhlcData, trades: readonly Trade[]): Record<string, any> => {
  const categoryData = ohlc.datetime
  const ohlcValues = ohlc.open.map((_, i) => [
    ohlc.open[i],
    ohlc.close[i],
    ohlc.low[i],
    ohlc.high[i],
  ])

  const tradeMarkLines = buildTradeMarkLines(trades)

  return {
    animation: false,
    tooltip: {
      animation: false,
      transitionDuration: 0,
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      position: (_pos: number[], _params: any, _el: any, _elRect: any, size: any) => {
        return { top: -10, right: size.viewSize[0] - size.contentSize[0] - 10 }
      },
    },
    grid: {
      left: '3%',
      right: '3%',
      top: '5%',
      bottom: '15%',
    },
    xAxis: {
      type: 'category',
      data: categoryData,
      boundaryGap: false,
      axisLabel: {
        formatter: (value: string) => formatDatetime(value),
      },
    },
    yAxis: {
      scale: true,
      splitArea: { show: true },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%' },
    ],
    series: [
      {
        name: 'Candlestick',
        type: 'candlestick',
        data: ohlcValues,
        itemStyle: {
          color: CHART_COLORS.candleUp,
          color0: CHART_COLORS.candleDown,
          borderColor: CHART_COLORS.candleUpBorder,
          borderColor0: CHART_COLORS.candleDownBorder,
        },
        markLine: {
          symbol: ['none', 'triangle'],
          symbolSize: 10,
          label: {
            show: true,
            formatter: (params: any) => params.data?.name ?? '',
            position: 'end',
            fontSize: 10,
          },
          tooltip: {
            animation: false,
            transitionDuration: 0,
            trigger: 'item',
            position: (pos: number[], _params: any, _el: any, _elRect: any, size: any) => {
              const chartMidX = size.viewSize[0] / 2
              if (pos[0] > chartMidX) {
                return { top: 10, left: 10 }
              }
              return { top: 10, right: 10 }
            },
            formatter: (params: any) => {
              const trade = params.data?.trade
              if (!trade) return params.data?.name ?? ''
              return formatTradeTooltip(trade)
            },
          },
          emphasis: {
            lineStyle: { width: 4 },
          },
          lineStyle: {
            type: 'solid',
            width: 2,
          },
          data: tradeMarkLines,
        },
      },
    ],
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export const CandlestickChart = ({ ohlc, trades, onChartReady }: CandlestickChartProps) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = echarts.init(containerRef.current)
    chartRef.current = chart
    onChartReady?.(chart)

    const option = buildOption(ohlc, trades)
    chart.setOption(option)

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [ohlc, trades, onChartReady])

  return <div ref={containerRef} style={{ width: '100%', height: '600px' }} />
}
