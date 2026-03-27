export type RunSummary = {
  readonly run_id: string
  readonly trader_id: string
  readonly strategy: string
  readonly total_positions: number
  readonly total_fills: number
  readonly total_pnl: number | null
  readonly win_rate: number | null
  readonly expectancy: number | null
  readonly sharpe_ratio: number | null
  readonly avg_win: number | null
  readonly avg_loss: number | null
  readonly win_loss_ratio: number | null
  readonly wins: number | null
  readonly losses: number | null
  readonly avg_hold_hours: number | null
  readonly pnl_per_week: number | null
  readonly trades_per_week: number | null
}

export type RunsResponse = {
  readonly runs: readonly RunSummary[]
  readonly total: number
  readonly page: number
  readonly per_page: number
}

export type RunDetail = {
  readonly run_id: string
  readonly config: Record<string, unknown>
  readonly total_fills: number
  readonly total_positions: number
  readonly bar_types: readonly string[]
}

export type Trade = {
  readonly relative_id: number
  readonly position_id: string
  readonly instrument_id: string
  readonly direction: 'Long' | 'Short'
  readonly entry_datetime: string
  readonly entry_price: number
  readonly exit_datetime: string
  readonly exit_price: number
  readonly quantity: number
  readonly pnl: number
  readonly currency: string
}

export type OhlcData = {
  readonly datetime: readonly string[]
  readonly open: readonly number[]
  readonly high: readonly number[]
  readonly low: readonly number[]
  readonly close: readonly number[]
  readonly volume: readonly number[]
}

export type EquityPoint = {
  readonly timestamp: string
  readonly equity: number
}

export type Fill = {
  readonly client_order_id: string
  readonly venue_order_id: string
  readonly trade_id: string
  readonly position_id: string
  readonly instrument_id: string
  readonly order_side: string
  readonly order_type: string
  readonly last_qty: string
  readonly last_px: string
  readonly currency: string
  readonly commission: string
  readonly ts_event: string
}

export type Position = {
  readonly position_id: string
  readonly instrument_id: string
  readonly strategy_id: string
  readonly entry: string
  readonly side: string
  readonly quantity: number
  readonly peak_qty: number
  readonly avg_px_open: number
  readonly avg_px_close: number
  readonly realized_return: number
  readonly realized_pnl: number
  readonly currency: string
  readonly ts_opened: string
  readonly ts_closed: string
  readonly duration_ns: number
}

export type TradeCategory = {
  readonly id: number
  readonly description: string
  readonly tradeIds: ReadonlySet<number>
}

export type IndicatorMeta = {
  readonly id: string
  readonly label: string
  readonly display: "overlay" | "panel"
  readonly outputs: readonly string[]
}

export type IndicatorResult = {
  readonly id: string
  readonly label: string
  readonly display: "overlay" | "panel"
  readonly outputs: Readonly<Record<string, readonly (number | null)[]>>
  readonly datetime: readonly string[]
}

export type CatalogEntry = {
  readonly instrument: string
  readonly bar_count: number
  readonly start_date: string
  readonly end_date: string
  readonly timeframe: string
}
