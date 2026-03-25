import { useState, useCallback, useRef, useEffect } from 'react'
import type { Trade, OhlcData } from '@/types/api'
import type * as echarts from 'echarts'
import { findBarIndex } from '@/lib/trade-utils'

export const useTradeNavigation = (
  trades: readonly Trade[],
  ohlc: OhlcData | undefined,
  chartInstance: echarts.ECharts | null,
) => {
  const [currentIndex, setCurrentIndex] = useState(0)

  // Sync refs on every render so callbacks always read latest values
  const chartRef = useRef(chartInstance)
  chartRef.current = chartInstance
  const ohlcRef = useRef(ohlc)
  ohlcRef.current = ohlc
  const tradesRef = useRef(trades)
  tradesRef.current = trades

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

    // Zoom to 5x trade length, centered on the trade (min 50 bars)
    const tradeLen = Math.max(exitIdx - entryIdx, 1)
    const viewLen = Math.max(tradeLen * 5, 50)
    const padding = (viewLen - tradeLen) / 2
    const startIdx = Math.max(0, Math.round(entryIdx - padding))
    const endIdx = Math.min(totalBars - 1, Math.round(exitIdx + padding))

    const startPercent = (startIdx / totalBars) * 100
    const endPercent = (endIdx / totalBars) * 100

    chart.dispatchAction({
      type: 'dataZoom',
      start: startPercent,
      end: endPercent,
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
