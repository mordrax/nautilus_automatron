/**
 * Renders lifecycle-tracked KeyLevel DTOs as eCharts markLine segments.
 *
 * The chart's x-axis is `type: 'category'` with ISO 8601 datetime strings as
 * labels. eCharts' `coord: [x, y]` on a category axis must reference an
 * existing label *value* — not an arbitrary timestamp — so we snap each
 * level's start/end timestamp to its nearest matching label.
 *
 * ISO 8601 strings with consistent timezone sort lexicographically the same
 * way they sort chronologically, so we can binary-search on plain strings.
 */

import type { KeyLevelDto } from '@/types/key-levels'

type KeyLevelStyle = {
  readonly color: string
  readonly baseWidth: number
}

const SOURCE_STYLE: Record<string, KeyLevelStyle> = {
  equal_highs_lows: { color: '#5470c6', baseWidth: 1.5 },
  wick_rejection: { color: '#ee6666', baseWidth: 1.5 },
  atr_volatility: { color: '#fac858', baseWidth: 1.5 },
  fib_retracement: { color: '#91cc75', baseWidth: 1.5 },
  fib_extension: { color: '#91cc75', baseWidth: 1.5 },
  pivot_standard: { color: '#73c0de', baseWidth: 1.5 },
  pivot_fibonacci: { color: '#73c0de', baseWidth: 1.5 },
  pivot_camarilla: { color: '#73c0de', baseWidth: 1.5 },
  pivot_woodie: { color: '#73c0de', baseWidth: 1.5 },
  pivot_demark: { color: '#73c0de', baseWidth: 1.5 },
  psychological: { color: '#9a60b4', baseWidth: 1.5 },
  volume_profile: { color: '#ea7ccc', baseWidth: 1.5 },
  volume_distribution: { color: '#3ba272', baseWidth: 1.5 },
  anchored_vwap: { color: '#fc8452', baseWidth: 1.5 },
  cvd: { color: '#27727b', baseWidth: 1.5 },
  session_level: { color: '#3d5499', baseWidth: 1.5 },
  periodic_level: { color: '#d48265', baseWidth: 1.5 },
  opening_range: { color: '#759aa0', baseWidth: 1.5 },
  market_profile_tpo: { color: '#c1232b', baseWidth: 1.5 },
  swing_cluster: { color: '#b5c334', baseWidth: 1.5 },
  order_block: { color: '#dd6b66', baseWidth: 1.5 },
  fair_value_gap: { color: '#e69d87', baseWidth: 1.5 },
  price_gap: { color: '#8dc1a9', baseWidth: 1.5 },
  darvas_box: { color: '#ea7e53', baseWidth: 1.5 },
  consolidation_zone: { color: '#eedd78', baseWidth: 1.5 },
}

const DEFAULT_STYLE: KeyLevelStyle = { color: '#888', baseWidth: 1.5 }

/**
 * Snap a timestamp to the nearest existing category label. Uses binary
 * search on lexicographic ordering (valid for consistent-timezone ISO 8601).
 *
 * - ts before first label → first label
 * - ts after last label → last label
 * - exact match → that label
 * - between two labels → the *earlier* one (start cell of the bucket)
 */
export const snapToCategory = (
  ts: string,
  labels: readonly string[],
): string => {
  if (labels.length === 0) return ts
  if (ts <= labels[0]) return labels[0]
  if (ts >= labels[labels.length - 1]) return labels[labels.length - 1]

  let lo = 0
  let hi = labels.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >>> 1
    if (labels[mid] <= ts) lo = mid
    else hi = mid - 1
  }
  return labels[lo]
}

/* eslint-disable @typescript-eslint/no-explicit-any */
type EChartsSeries = Record<string, any>

type MarkLineSegment = readonly [
  Record<string, any>,
  Record<string, any>,
]

const buildSegment = (
  level: KeyLevelDto,
  labels: readonly string[],
): MarkLineSegment => {
  const style = SOURCE_STYLE[level.source] ?? DEFAULT_STYLE
  const startLabel = snapToCategory(level.start_ts, labels)
  const endLabel = level.end_ts !== null
    ? snapToCategory(level.end_ts, labels)
    : labels[labels.length - 1]

  // Clamp strength to [0, 1] before mapping to width/opacity so detector
  // bugs can't blow up the chart.
  const s = Math.max(0, Math.min(1, level.strength))
  const width = style.baseWidth + 2 * s
  const opacity = 0.25 + 0.65 * s

  return [
    {
      coord: [startLabel, level.price],
      lineStyle: { color: style.color, width, opacity },
      // Tag so the existing trade-markLine click handler (which keys on
      // `params.data?.trade`) ignores these.
      keyLevel: true,
    },
    {
      coord: [endLabel, level.price],
    },
  ] as const
}

export const buildKeyLevelSeries = (
  levels: readonly KeyLevelDto[],
  datetimeLabels: readonly string[],
): EChartsSeries => {
  if (levels.length === 0 || datetimeLabels.length === 0) {
    return {
      name: 'Key Levels',
      type: 'line',
      data: [],
      showSymbol: false,
      silent: true,
      markLine: {
        symbol: ['none', 'none'],
        label: { show: false },
        data: [],
      },
    }
  }

  const segments = levels.map((lvl) => buildSegment(lvl, datetimeLabels))

  return {
    name: 'Key Levels',
    type: 'line',
    data: [],
    showSymbol: false,
    silent: true,
    markLine: {
      symbol: ['none', 'none'],
      label: { show: false },
      data: segments,
    },
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any */
