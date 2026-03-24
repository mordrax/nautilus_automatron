import { CHART_COLORS } from './chart-config'
import type { Trade } from '@/types/api'

export const buildTradeMarkLines = (trades: readonly Trade[]) =>
  trades.map((trade) => [
    {
      coord: [trade.entry_datetime, trade.entry_price],
      lineStyle: {
        color: trade.pnl > 0 ? CHART_COLORS.tradeWin : CHART_COLORS.tradeLoss,
      },
      name: `#${trade.relative_id}`,
      trade,
    },
    {
      coord: [trade.exit_datetime, trade.exit_price],
    },
  ])

export const formatPrice = (price: number, precision: number = 5): string =>
  price.toFixed(precision)

export const formatPnl = (pnl: number): string =>
  `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`

export const formatDatetime = (iso: string): string => {
  const d = new Date(iso)
  const month = d.toLocaleString('en', { month: 'short' })
  const day = d.getDate()
  const hours = d.getHours().toString().padStart(2, '0')
  const mins = d.getMinutes().toString().padStart(2, '0')
  return `${month}-${day} ${hours}:${mins}`
}

export const formatTradeTooltip = (trade: Trade): string => {
  const pnlColor = trade.pnl >= 0 ? CHART_COLORS.tradeWin : CHART_COLORS.tradeLoss
  return [
    `<b>Trade #${trade.relative_id}</b>`,
    `<b>Direction:</b> ${trade.direction}`,
    `<b>Entry:</b> ${formatDatetime(trade.entry_datetime)} @ ${formatPrice(trade.entry_price)}`,
    `<b>Exit:</b> ${formatDatetime(trade.exit_datetime)} @ ${formatPrice(trade.exit_price)}`,
    `<b>Qty:</b> ${trade.quantity}`,
    `<b>PnL:</b> <span style="color:${pnlColor}">${formatPnl(trade.pnl)} ${trade.currency}</span>`,
  ].join('<br/>')
}

export const findBarIndex = (datetimes: readonly string[], target: string): number => {
  const targetTime = new Date(target).getTime()
  let closest = 0
  let minDiff = Infinity
  for (let i = 0; i < datetimes.length; i++) {
    const diff = Math.abs(new Date(datetimes[i]).getTime() - targetTime)
    if (diff < minDiff) {
      minDiff = diff
      closest = i
    }
  }
  return closest
}
