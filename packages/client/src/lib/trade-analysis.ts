import type { Trade } from '@/types/api'

export type PnlBin = {
  readonly center: number
  readonly count: number
  readonly isPositive: boolean
}

export const computePnlDistribution = (trades: readonly Trade[], binCount: number = 40): readonly PnlBin[] => {
  if (trades.length === 0) return []

  const pnls = trades.map(t => t.pnl)
  const min = pnls.reduce((a, b) => Math.min(a, b), Infinity)
  const max = pnls.reduce((a, b) => Math.max(a, b), -Infinity)

  if (min === max) {
    return [{ center: min, count: trades.length, isPositive: min >= 0 }]
  }

  const binWidth = (max - min) / binCount
  const counts = new Array<number>(binCount).fill(0)

  for (const pnl of pnls) {
    const idx = Math.min(Math.floor((pnl - min) / binWidth), binCount - 1)
    counts[idx]++
  }

  return counts.map((count, i) => {
    const center = min + (i + 0.5) * binWidth
    return { center, count, isPositive: center >= 0 }
  })
}

export const computeHoldTimeHours = (trade: Trade): number => {
  const entry = new Date(trade.entry_datetime).getTime()
  const exit = new Date(trade.exit_datetime).getTime()
  return (exit - entry) / (1000 * 60 * 60)
}
