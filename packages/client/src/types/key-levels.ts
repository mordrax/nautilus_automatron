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
