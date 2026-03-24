import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { buildTradeMarkLines, formatTradeTooltip, formatDatetime } from '@/lib/trade-utils'
import type { OhlcData, Trade } from '@/types/api'

type CandlestickChartProps = {
  readonly ohlc: OhlcData
  readonly trades: readonly Trade[]
  readonly currentTradeIndex: number
  readonly onSelectTrade: (index: number) => void
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

const TOOLTIP_STYLE = [
  'position:absolute',
  'pointer-events:none',
  'z-index:9999',
  'padding:8px 12px',
  'background:rgba(0,0,0,0.85)',
  'color:#fff',
  'border-radius:4px',
  'font-size:13px',
  'line-height:1.6',
  'white-space:nowrap',
].join(';')

const updateTradeTooltip = (
  el: HTMLDivElement,
  trade: Trade | undefined,
) => {
  if (!trade) {
    el.style.display = 'none'
    return
  }
  el.innerHTML = formatTradeTooltip(trade)
  el.style.display = 'block'
  // Position: if tooltip is wider than half the container, pin left; otherwise pin right
  // We always show top-left for now, the OHLC tooltip is top-right
  el.style.top = '10px'
  el.style.left = '10px'
  el.style.right = ''
}

export const CandlestickChart = ({
  ohlc,
  trades,
  currentTradeIndex,
  onSelectTrade,
  onChartReady,
}: CandlestickChartProps) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)

  // Build chart once
  useEffect(() => {
    if (!containerRef.current) return

    const chart = echarts.init(containerRef.current)
    chartRef.current = chart
    onChartReady?.(chart)

    const option = buildOption(ohlc, trades)
    chart.setOption(option)

    // Create persistent trade tooltip element
    const tooltipEl = document.createElement('div')
    tooltipEl.style.cssText = TOOLTIP_STYLE
    containerRef.current.style.position = 'relative'
    containerRef.current.appendChild(tooltipEl)
    tooltipRef.current = tooltipEl

    // Set initial content
    updateTradeTooltip(tooltipEl, trades[currentTradeIndex])

    // Click on markLine selects that trade
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    chart.on('click', { componentType: 'markLine' }, (params: any) => {
      const trade = params.data?.trade
      if (!trade) return
      const idx = trades.findIndex((t) => t.relative_id === trade.relative_id)
      if (idx >= 0) onSelectTrade(idx)
    })

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      tooltipEl.remove()
      chart.dispose()
      chartRef.current = null
      tooltipRef.current = null
    }
  }, [ohlc, trades, onChartReady, onSelectTrade])

  // Update tooltip content when current trade changes
  useEffect(() => {
    if (!tooltipRef.current || !containerRef.current) return
    const trade = trades[currentTradeIndex]
    updateTradeTooltip(tooltipRef.current, trade)
  }, [currentTradeIndex, trades])

  return <div ref={containerRef} style={{ width: '100%', height: '600px' }} />
}
