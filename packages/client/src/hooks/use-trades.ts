import { useState, useCallback } from 'react'
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

  const centerOnTrade = useCallback(
    (index: number) => {
      if (!chartInstance || !ohlc || trades.length === 0) return

      const trade = trades[index]
      if (!trade) return

      const entryIdx = findBarIndex(ohlc.datetime, trade.entry_datetime)
      const exitIdx = findBarIndex(ohlc.datetime, trade.exit_datetime)

      const totalBars = ohlc.datetime.length
      const startIdx = Math.max(0, entryIdx - ZOOM_PADDING)
      const endIdx = Math.min(totalBars - 1, exitIdx + ZOOM_PADDING)

      const startPercent = (startIdx / totalBars) * 100
      const endPercent = (endIdx / totalBars) * 100

      chartInstance.dispatchAction({
        type: 'dataZoom',
        start: startPercent,
        end: endPercent,
      })
    },
    [chartInstance, ohlc, trades],
  )

  const navigateTrade = useCallback(
    (direction: number) => {
      if (trades.length === 0) return
      const newIndex = ((currentIndex + direction) % trades.length + trades.length) % trades.length
      setCurrentIndex(newIndex)
      centerOnTrade(newIndex)
    },
    [currentIndex, trades.length, centerOnTrade],
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
