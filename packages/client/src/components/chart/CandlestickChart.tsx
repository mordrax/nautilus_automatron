import { useRef, useEffect, useState, useCallback } from 'react'
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
      trigger: 'axis',
      axisPointer: { type: 'cross' },
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

type TooltipPosition = { readonly x: number; readonly y: number }

const TradeTooltip = ({ trade }: { readonly trade: Trade | undefined }) => {
  const [pos, setPos] = useState<TooltipPosition>({ x: 10, y: 10 })
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y }

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return
      setPos({
        x: dragRef.current.origX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.origY + (ev.clientY - dragRef.current.startY),
      })
    }

    const onMouseUp = () => {
      dragRef.current = null
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [pos])

  if (!trade) return null
  return (
    <div
      onMouseDown={onMouseDown}
      style={{
        position: 'absolute',
        top: pos.y,
        left: pos.x,
        zIndex: 9999,
        padding: '8px 12px',
        background: 'rgba(0,0,0,0.85)',
        color: '#fff',
        borderRadius: 4,
        fontSize: 13,
        lineHeight: 1.6,
        whiteSpace: 'nowrap',
        cursor: 'grab',
        userSelect: 'none',
      }}
      dangerouslySetInnerHTML={{ __html: formatTradeTooltip(trade) }}
    />
  )
}

export const CandlestickChart = ({
  ohlc,
  trades,
  currentTradeIndex,
  onSelectTrade,
  onChartReady,
}: CandlestickChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const [selectTradeRef] = useState(() => ({ current: onSelectTrade }))
  selectTradeRef.current = onSelectTrade

  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chartRef.current = chart
    onChartReady?.(chart)

    const option = buildOption(ohlc, trades)
    chart.setOption(option)

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    chart.on('click', { componentType: 'markLine' }, (params: any) => {
      const trade = params.data?.trade
      if (!trade) return
      const idx = trades.findIndex((t) => t.relative_id === trade.relative_id)
      if (idx >= 0) selectTradeRef.current(idx)
    })

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [ohlc, trades, onChartReady])

  const currentTrade = trades[currentTradeIndex]

  return (
    <div style={{ position: 'relative', width: '100%', height: '600px' }}>
      <div ref={chartDivRef} style={{ width: '100%', height: '100%' }} />
      <TradeTooltip trade={currentTrade} />
    </div>
  )
}
