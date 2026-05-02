export const CHART_COLORS = {
  tradeWin: '#7FD373',
  tradeLoss: '#F68EA3',
  candleUp: '#7FD373',
  candleUpBorder: '#2B6D22',
  candleDown: '#F68EA3',
  candleDownBorder: '#970C28',
  entrySignal: '#FFA250',
  exitSignal: '#556577',
} as const

export const INDICATOR_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
] as const

/**
 * Get a deterministic default color for an indicator by its ID.
 * Uses a simple hash so the same indicator always gets the same color
 * regardless of which other indicators are enabled.
 */
export const getDefaultIndicatorColor = (id: string): string => {
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash + id.charCodeAt(i)) | 0
  }
  return INDICATOR_COLORS[Math.abs(hash) % INDICATOR_COLORS.length]
}
