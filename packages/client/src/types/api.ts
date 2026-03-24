export type RunSummary = {
  readonly run_id: string
  readonly trader_id: string
  readonly strategy: string
  readonly total_positions: number
  readonly total_fills: number
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
