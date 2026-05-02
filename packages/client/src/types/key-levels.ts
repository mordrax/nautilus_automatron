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

export type SourceMetaDto = EqualHighsLowsMetaDto

export type KeyLevelSource = 'equal_highs_lows'

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
