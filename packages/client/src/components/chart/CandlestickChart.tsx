import { useRef, useEffect, useState, useCallback } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS, INDICATOR_COLORS } from '@/lib/chart-config'
import { buildTradeMarkLines, formatTradeTooltip, formatDatetime } from '@/lib/trade-utils'
import type { OhlcData, Trade, IndicatorResult } from '@/types/api'

type CandlestickChartProps = {
  readonly ohlc: OhlcData
  readonly trades?: readonly Trade[]
  readonly indicators?: readonly IndicatorResult[]
  readonly currentTradeIndex?: number
  readonly onSelectTrade?: (index: number) => void
  readonly onChartReady?: (chart: echarts.ECharts) => void
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const buildIndicatorOverlaySeries = (
  indicators: readonly IndicatorResult[],
  colorOffset: number,
): any[] => {
  const series: any[] = []
  let colorIdx = colorOffset

  for (const ind of indicators) {
    if (ind.display !== 'overlay') continue
    for (const field of Object.keys(ind.outputs)) {
      const color = INDICATOR_COLORS[colorIdx % INDICATOR_COLORS.length]
      colorIdx++
      series.push({
        name: Object.keys(ind.outputs).length > 1 ? `${ind.label} ${field}` : ind.label,
        type: 'line',
        data: ind.outputs[field],
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 1.5, color },
        itemStyle: { color },
        xAxisIndex: 0,
        yAxisIndex: 0,
      })
    }
  }

  return series
}

const buildPanelConfig = (
  indicators: readonly IndicatorResult[],
  colorOffset: number,
) => {
  const panelIndicators = indicators.filter(i => i.display === 'panel')
  const grids: any[] = []
  const xAxes: any[] = []
  const yAxes: any[] = []
  const series: any[] = []
  let colorIdx = colorOffset

  const dataZoomHeight = 40 // space for the slider at the bottom
  const panelHeight = 100
  const panelGap = 30 // gap between panels

  panelIndicators.forEach((ind, panelIdx) => {
    const gridIdx = panelIdx + 1 // 0 is main chart
    const panelCount = panelIndicators.length
    const bottomOffset = dataZoomHeight + (panelCount - 1 - panelIdx) * (panelHeight + panelGap)

    grids.push({
      left: '3%',
      right: '3%',
      height: `${panelHeight}px`,
      bottom: `${bottomOffset}px`,
    })

    const isBottomPanel = panelIdx === panelIndicators.length - 1
    xAxes.push({
      type: 'category',
      gridIndex: gridIdx,
      data: ind.datetime,
      boundaryGap: false,
      axisLabel: isBottomPanel
        ? { formatter: (value: string) => formatDatetime(value), fontSize: 10 }
        : { show: false },
      axisTick: { show: isBottomPanel },
    })

    yAxes.push({
      scale: true,
      gridIndex: gridIdx,
      splitNumber: 3,
      axisLabel: { fontSize: 10 },
      name: ind.label,
      nameTextStyle: { fontSize: 10, padding: [0, 40, 0, 0] },
    })

    for (const field of Object.keys(ind.outputs)) {
      const color = INDICATOR_COLORS[colorIdx % INDICATOR_COLORS.length]
      colorIdx++
      series.push({
        name: Object.keys(ind.outputs).length > 1 ? `${ind.label} ${field}` : ind.label,
        type: 'line',
        data: ind.outputs[field],
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 1.5, color },
        itemStyle: { color },
        xAxisIndex: gridIdx,
        yAxisIndex: gridIdx,
      })
    }
  })

  return { grids, xAxes, yAxes, series, panelCount: panelIndicators.length }
}

const buildOption = (
  ohlc: OhlcData,
  trades: readonly Trade[],
  indicators: readonly IndicatorResult[],
): Record<string, any> => {
  const categoryData = ohlc.datetime
  const ohlcValues = ohlc.open.map((_, i) => [
    ohlc.open[i],
    ohlc.close[i],
    ohlc.low[i],
    ohlc.high[i],
  ])

  const tradeMarkLines = buildTradeMarkLines(trades)

  const overlaySeries = buildIndicatorOverlaySeries(indicators, 0)
  const overlayColorCount = indicators
    .filter(i => i.display === 'overlay')
    .reduce((acc, ind) => acc + Object.keys(ind.outputs).length, 0)
  const panels = buildPanelConfig(indicators, overlayColorCount)

  const mainGridBottom = panels.panelCount > 0
    ? `${40 + panels.panelCount * 130 + 40}px`
    : '15%'

  const allXAxisIndices = [0, ...panels.xAxes.map((_: any, i: number) => i + 1)]

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    grid: [
      {
        left: '3%',
        right: '3%',
        top: '5%',
        bottom: mainGridBottom,
      },
      ...panels.grids,
    ],
    xAxis: [
      {
        type: 'category',
        data: categoryData,
        boundaryGap: false,
        axisLabel: panels.panelCount > 0
          ? { show: false }
          : { formatter: (value: string) => formatDatetime(value) },
        axisTick: { show: panels.panelCount === 0 },
      },
      ...panels.xAxes,
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: true },
      },
      ...panels.yAxes,
    ],
    dataZoom: [
      { type: 'inside', start: 0, end: 100, xAxisIndex: allXAxisIndices },
      { type: 'slider', start: 0, end: 100, bottom: '2%', xAxisIndex: allXAxisIndices },
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
      ...overlaySeries,
      ...panels.series,
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
        x: dragRef.current.origX - (ev.clientX - dragRef.current.startX),
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
        right: pos.x,
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
  trades = [],
  indicators = [],
  currentTradeIndex,
  onSelectTrade,
  onChartReady,
}: CandlestickChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const selectTradeRef = useRef(onSelectTrade)

  useEffect(() => {
    selectTradeRef.current = onSelectTrade
  })

  const panelCount = indicators.filter(i => i.display === 'panel').length
  const chartHeight = 600 + panelCount * 150

  // Init chart and bind click on ohlc/trades change (destroys + recreates)
  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chartRef.current = chart
    onChartReady?.(chart)

    const option = buildOption(ohlc, trades, indicators)
    chart.setOption(option)

    // Expose chart for e2e testing
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).__ECHARTS_INSTANCE__ = chart

    if (selectTradeRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      chart.on('click', { componentType: 'markLine' }, (params: any) => {
        const trade = params.data?.trade
        if (!trade) return
        const idx = trades.findIndex((t) => t.relative_id === trade.relative_id)
        if (idx >= 0) selectTradeRef.current?.(idx)
      })
    }

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
      chartRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- indicators handled by the update effect below; selectTradeRef is a stable ref
  }, [ohlc, trades, onChartReady])

  // Update indicators without destroying chart (preserves zoom/state)
  useEffect(() => {
    if (!chartRef.current) return
    const fullOption = buildOption(ohlc, trades, indicators)

    // Preserve current zoom position but update xAxisIndex for new/removed panels
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const currentOption = chartRef.current.getOption() as Record<string, any>
    const currentStart = currentOption.dataZoom?.[0]?.start ?? 0
    const currentEnd = currentOption.dataZoom?.[0]?.end ?? 100
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    fullOption.dataZoom = fullOption.dataZoom.map((dz: any) => ({
      ...dz,
      start: currentStart,
      end: currentEnd,
    }))

    chartRef.current.setOption(fullOption, { replaceMerge: ['series', 'grid', 'xAxis', 'yAxis'] })
    chartRef.current.resize()
  }, [ohlc, trades, indicators])

  const showTooltip = trades.length > 0 && currentTradeIndex !== undefined
  const currentTrade = showTooltip ? trades[currentTradeIndex] : undefined

  return (
    <div data-testid="chart-container" style={{ position: 'relative', width: '100%', height: `${chartHeight}px` }}>
      <div ref={chartDivRef} style={{ width: '100%', height: '100%' }} />
      {showTooltip && <TradeTooltip trade={currentTrade} />}
    </div>
  )
}
