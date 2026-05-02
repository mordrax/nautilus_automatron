/**
 * Frontend DTOs mirroring `packages/server/server/store/key_levels.py`.
 *
 * Keep in sync with the backend Pydantic models. Discriminated by `kind` on
 * the `meta` union so adding a new detector is additive on both sides.
 */

export type EqualHighsLowsMetaDto = {
  readonly kind: 'equal_highs_lows'
  readonly touch_prices: readonly number[]
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type WickRejectionMetaDto = {
  readonly kind: 'wick_rejection'
  readonly rejection_count: number
  readonly avg_wick_ratio: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type AtrVolatilityMetaDto = {
  readonly kind: 'atr_volatility'
  readonly atr_value: number
  readonly multiplier: number
  readonly anchor_price: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type FibonacciMetaDto = {
  readonly kind: 'fibonacci'
  readonly ratio: number
  readonly swing_high: number
  readonly swing_low: number
  readonly direction: 'retracement' | 'extension'
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type PivotPointMetaDto = {
  readonly kind: 'pivot_point'
  readonly variant: 'standard' | 'fibonacci' | 'camarilla' | 'woodie' | 'demark'
  readonly level_name: string
  readonly period_high: number
  readonly period_low: number
  readonly period_close: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type PsychologicalMetaDto = {
  readonly kind: 'psychological'
  readonly tier: 'major' | 'minor' | 'micro'
  readonly round_value: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type VolumeProfileMetaDto = {
  readonly kind: 'volume_profile'
  readonly volume_concentration: number
  readonly node_type: 'poc' | 'hvn' | 'lvn' | 'va_high' | 'va_low'
  readonly bin_volume: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type VolumeDistributionMetaDto = {
  readonly kind: 'volume_distribution'
  readonly context: 'consolidation' | 'peak' | 'trough' | 'range'
  readonly volume_concentration: number
  readonly context_bar_count: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type AnchoredVwapMetaDto = {
  readonly kind: 'anchored_vwap'
  readonly anchor_ts: number
  readonly anchor_type: 'swing_high' | 'swing_low' | 'gap' | 'volume_spike'
  readonly cumulative_volume: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type CvdMetaDto = {
  readonly kind: 'cvd'
  readonly cvd_value: number
  readonly divergence: 'bullish' | 'bearish' | 'none'
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type SessionLevelMetaDto = {
  readonly kind: 'session_level'
  readonly session: 'asian' | 'london' | 'new_york' | 'custom'
  readonly role: 'high' | 'low'
  readonly session_date_iso: string
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type PeriodicLevelMetaDto = {
  readonly kind: 'periodic_level'
  readonly period: 'daily' | 'weekly' | 'monthly'
  readonly role: 'high' | 'low'
  readonly period_start_iso: string
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type OpeningRangeMetaDto = {
  readonly kind: 'opening_range'
  readonly range_minutes: number
  readonly role: 'high' | 'low'
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type MarketProfileMetaDto = {
  readonly kind: 'market_profile_tpo'
  readonly tpo_count: number
  readonly role: 'poc' | 'vah' | 'val'
  readonly total_tpo_periods: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type SwingClusterMetaDto = {
  readonly kind: 'swing_cluster'
  readonly cluster_radius: number
  readonly pivot_indices: readonly number[]
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type OrderBlockMetaDto = {
  readonly kind: 'order_block'
  readonly block_side: 'bullish' | 'bearish'
  readonly displacement_atr_multiple: number
  readonly block_open: number
  readonly block_close: number
  readonly mitigation_pct: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type FairValueGapMetaDto = {
  readonly kind: 'fair_value_gap'
  readonly gap_side: 'bullish' | 'bearish'
  readonly gap_size: number
  readonly fill_percentage: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type PriceGapMetaDto = {
  readonly kind: 'price_gap'
  readonly gap_type: 'breakaway' | 'runaway' | 'exhaustion' | 'common'
  readonly gap_size: number
  readonly fill_percentage: number
  readonly level_type: 'upper' | 'lower'
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type DarvasBoxMetaDto = {
  readonly kind: 'darvas_box'
  readonly box_top: number
  readonly box_bottom: number
  readonly confirmed: boolean
  readonly bars_in_box: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type ConsolidationZoneMetaDto = {
  readonly kind: 'consolidation_zone'
  readonly range_high: number
  readonly range_low: number
  readonly slope: number
  readonly bar_count: number
  readonly duration_bars: number
  readonly range_atr_multiple: number
  readonly side: 'high' | 'low'
  readonly touch_count: number
}

export type SourceMetaDto =
  | EqualHighsLowsMetaDto
  | WickRejectionMetaDto
  | AtrVolatilityMetaDto
  | FibonacciMetaDto
  | PivotPointMetaDto
  | PsychologicalMetaDto
  | VolumeProfileMetaDto
  | VolumeDistributionMetaDto
  | AnchoredVwapMetaDto
  | CvdMetaDto
  | SessionLevelMetaDto
  | PeriodicLevelMetaDto
  | OpeningRangeMetaDto
  | MarketProfileMetaDto
  | SwingClusterMetaDto
  | OrderBlockMetaDto
  | FairValueGapMetaDto
  | PriceGapMetaDto
  | DarvasBoxMetaDto
  | ConsolidationZoneMetaDto

export type KeyLevelSource =
  | 'equal_highs_lows'
  | 'wick_rejection'
  | 'atr_volatility'
  | 'fib_retracement'
  | 'fib_extension'
  | 'pivot_standard'
  | 'pivot_fibonacci'
  | 'pivot_camarilla'
  | 'pivot_woodie'
  | 'pivot_demark'
  | 'psychological'
  | 'volume_profile'
  | 'volume_distribution'
  | 'anchored_vwap'
  | 'cvd'
  | 'session_level'
  | 'periodic_level'
  | 'opening_range'
  | 'market_profile_tpo'
  | 'swing_cluster'
  | 'order_block'
  | 'fair_value_gap'
  | 'price_gap'
  | 'darvas_box'
  | 'consolidation_zone'

export type KeyLevelDto = {
  readonly price: number
  readonly strength: number
  readonly start_ts: string
  readonly end_ts: string | null
  readonly source: KeyLevelSource
  readonly bounce_count: number
  readonly zone_upper: number | null
  readonly zone_lower: number | null
  readonly meta: SourceMetaDto
}

export type DetectorMeta = {
  readonly id: string
  readonly label: string
  readonly color: string
}
