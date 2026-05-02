"""Key Level data model and typed metadata.

All types are frozen dataclasses — immutable once created.
The SourceMeta discriminated union provides type-safe, per-detector metadata
without dict[str, Any] or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Source — which detector produced a level
# ---------------------------------------------------------------------------

Source = Literal[
    "swing_cluster",
    "equal_highs_lows",
    "wick_rejection",
    "pivot_standard",
    "pivot_fibonacci",
    "pivot_camarilla",
    "pivot_woodie",
    "pivot_demark",
    "fib_retracement",
    "fib_extension",
    "psychological",
    "atr_volatility",
    "volume_profile",
    "volume_distribution",
    "anchored_vwap",
    "cvd",
    "session_level",
    "periodic_level",
    "opening_range",
    "market_profile_tpo",
    "order_block",
    "fair_value_gap",
    "price_gap",
    "darvas_box",
    "consolidation_zone",
    "ma_confluence",
    "wyckoff_zone",
]

# ---------------------------------------------------------------------------
# Typed metadata per detector (discriminated union)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwingClusterMeta:
    cluster_radius: float
    pivot_indices: tuple[int, ...]
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class EqualHighsLowsMeta:
    touch_prices: tuple[float, ...]
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class WickRejectionMeta:
    rejection_count: int
    avg_wick_ratio: float
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class PivotPointMeta:
    variant: Literal["standard", "fibonacci", "camarilla", "woodie", "demark"]
    level_name: str
    period_high: float
    period_low: float
    period_close: float
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class FibonacciMeta:
    ratio: float
    swing_high: float
    swing_low: float
    direction: Literal["retracement", "extension"]
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class PsychologicalMeta:
    tier: Literal["major", "minor", "micro"]
    round_value: float
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class AtrVolatilityMeta:
    atr_value: float
    multiplier: float
    anchor_price: float
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class VolumeProfileMeta:
    volume_concentration: float
    node_type: Literal["poc", "hvn", "lvn", "va_high", "va_low"]
    bin_volume: float
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class VolumeDistributionMeta:
    context: Literal["consolidation", "peak", "trough", "range"]
    volume_concentration: float
    context_bar_count: int
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class AnchoredVwapMeta:
    anchor_ts: int
    anchor_type: Literal["swing_high", "swing_low", "gap", "volume_spike"]
    cumulative_volume: float
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class CvdMeta:
    cvd_value: float
    divergence: Literal["bullish", "bearish", "none"]
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class SessionLevelMeta:
    session: Literal["asian", "london", "new_york", "custom"]
    role: Literal["high", "low"]
    session_date_iso: str
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class PeriodicLevelMeta:
    period: Literal["daily", "weekly", "monthly"]
    role: Literal["high", "low"]
    period_start_iso: str
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class OpeningRangeMeta:
    range_minutes: int
    role: Literal["high", "low"]
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class MarketProfileMeta:
    tpo_count: int
    role: Literal["poc", "vah", "val"]
    total_tpo_periods: int
    side: Literal["high", "low"]
    touch_count: int


@dataclass(frozen=True)
class OrderBlockMeta:
    side: Literal["bullish", "bearish"]
    displacement_atr_multiple: float
    block_open: float
    block_close: float


@dataclass(frozen=True)
class FairValueGapMeta:
    side: Literal["bullish", "bearish"]
    gap_size: float
    fill_percentage: float


@dataclass(frozen=True)
class PriceGapMeta:
    gap_type: Literal["breakaway", "runaway", "exhaustion", "common"]
    gap_size: float
    fill_percentage: float
    level_type: Literal["upper", "lower"]


@dataclass(frozen=True)
class DarvasBoxMeta:
    box_top: float
    box_bottom: float
    confirmed: bool
    bars_in_box: int


@dataclass(frozen=True)
class ConsolidationZoneMeta:
    range_high: float
    range_low: float
    slope: float
    bar_count: int


@dataclass(frozen=True)
class MaConfluenceMeta:
    converging_periods: tuple[int, ...]
    spread_percent: float


@dataclass(frozen=True)
class WyckoffZoneMeta:
    phase: Literal["accumulation", "distribution"]
    event: Literal["sc", "ar", "st", "spring", "upthrust", "sos", "lpsy"]
    zone_high: float
    zone_low: float


SourceMeta = (
    SwingClusterMeta
    | EqualHighsLowsMeta
    | WickRejectionMeta
    | PivotPointMeta
    | FibonacciMeta
    | PsychologicalMeta
    | AtrVolatilityMeta
    | VolumeProfileMeta
    | VolumeDistributionMeta
    | AnchoredVwapMeta
    | CvdMeta
    | SessionLevelMeta
    | PeriodicLevelMeta
    | OpeningRangeMeta
    | MarketProfileMeta
    | OrderBlockMeta
    | FairValueGapMeta
    | PriceGapMeta
    | DarvasBoxMeta
    | ConsolidationZoneMeta
    | MaConfluenceMeta
    | WyckoffZoneMeta
)

# ---------------------------------------------------------------------------
# KeyLevel — the core output type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyLevel:
    """Lifecycle-tracked key level.

    A level has a start timestamp (when it became valid) and an optional end
    timestamp (when it was broken or aged out). `end_ts is None` means the
    level is still active at the end of the data stream.

    Zone fields are optional — only zoned detectors populate them; pure
    horizontals leave them as None.
    """

    price: float
    strength: float
    start_ts: int
    end_ts: int | None
    source: Source
    bounce_count: int
    zone_upper: float | None
    zone_lower: float | None
    meta: SourceMeta
