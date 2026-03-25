import { useState, useCallback, useRef, useEffect } from 'react'
import type { Trade, OhlcData } from '@/types/api'
import type * as echarts from 'echarts'
import { findBarIndex } from '@/lib/trade-utils'

const ZOOM_PADDING = 100

export const useTradeNavigation = (
  trades: readonly Trade[],
  ohlc: OhlcData | undefined,
  chartInstance: echarts.ECharts | null,
) => {
  const [currentIndex, setCurrentIndex] = useState(0)

  // Use refs to avoid stale closures in callbacks
  const chartRef = useRef(chartInstance)
  const ohlcRef = useRef(ohlc)
  const tradesRef = useRef(trades)

  useEffect(() => { chartRef.current = chartInstance }, [chartInstance])
  useEffect(() => { ohlcRef.current = ohlc }, [ohlc])
  useEffect(() => { tradesRef.current = trades }, [trades])

  const centerOnTrade = useCallback((index: number) => {
    const chart = chartRef.current
    const currentOhlc = ohlcRef.current
    const currentTrades = tradesRef.current

    if (!chart || !currentOhlc || currentTrades.length === 0) return

    const trade = currentTrades[index]
    if (!trade) return

    const totalBars = currentOhlc.datetime.length
    const entryIdx = findBarIndex(currentOhlc.datetime, trade.entry_datetime)
    const exitIdx = findBarIndex(currentOhlc.datetime, trade.exit_datetime)

    const entryPercent = (entryIdx / totalBars) * 100
    const exitPercent = (exitIdx / totalBars) * 100

    // Get current zoom window
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const opts = chart.getOption() as any
    const zoom = opts.dataZoom?.[0]
    const viewStart = zoom?.start ?? 0
    const viewEnd = zoom?.end ?? 100

    // Only pan if trade is outside the current viewport
    if (entryPercent >= viewStart && exitPercent <= viewEnd) return

    // Keep the same zoom width, just shift to center the trade
    const viewWidth = viewEnd - viewStart
    const tradeMid = (entryPercent + exitPercent) / 2
    const newStart = Math.max(0, tradeMid - viewWidth / 2)
    const newEnd = Math.min(100, newStart + viewWidth)

    chart.dispatchAction({
      type: 'dataZoom',
      start: newEnd === 100 ? 100 - viewWidth : newStart,
      end: newEnd,
    })
  }, [])

  const navigateTrade = useCallback(
    (direction: number) => {
      setCurrentIndex(prev => {
        const len = tradesRef.current.length
        if (len === 0) return prev
        const newIndex = ((prev + direction) % len + len) % len
        centerOnTrade(newIndex)
        return newIndex
      })
    },
    [centerOnTrade],
  )

  const selectTrade = useCallback(
    (index: number) => {
      setCurrentIndex(index)
      centerOnTrade(index)
    },
    [centerOnTrade],
  )

  return {
    currentIndex,
    currentTrade: trades[currentIndex] ?? null,
    navigateTrade,
    selectTrade,
  }
}
