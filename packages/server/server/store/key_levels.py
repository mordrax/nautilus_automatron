"""Key Level detector registry, DTOs, and compute path.

Lifecycle-tracked KeyLevels are produced by detectors and exposed via FastAPI
as Pydantic DTOs with a discriminated ``meta`` union — additive on both sides
as more detectors migrate to the event-based lifecycle model.
"""

from __future__ import annotations

from typing import Annotated, Callable, Literal, Protocol, Union

from pydantic import BaseModel, Field

from nautilus_trader.model.data import Bar

from indicators.key_levels.detectors.anchored_vwap import AnchoredVwapDetector
from indicators.key_levels.detectors.atr_volatility import AtrVolatilityDetector
from indicators.key_levels.detectors.cvd import CvdDetector
from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.detectors.fibonacci import (
    FibonacciExtensionDetector,
    FibonacciRetracementDetector,
)
from indicators.key_levels.detectors.market_profile import MarketProfileDetector
from indicators.key_levels.detectors.opening_range import OpeningRangeDetector
from indicators.key_levels.detectors.periodic_levels import PeriodicLevelDetector
from indicators.key_levels.detectors.pivot_points import PivotPointDetector
from indicators.key_levels.detectors.psychological import PsychologicalLevelDetector
from indicators.key_levels.detectors.session_levels import SessionLevelDetector
from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from indicators.key_levels.detectors.volume_distribution import (
    VolumeDistributionDetector,
)
from indicators.key_levels.detectors.volume_profile import VolumeProfileDetector
from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from indicators.key_levels.model import (
    AnchoredVwapMeta,
    AtrVolatilityMeta,
    CvdMeta,
    EqualHighsLowsMeta,
    FibonacciMeta,
    KeyLevel,
    MarketProfileMeta,
    OpeningRangeMeta,
    PeriodicLevelMeta,
    PivotPointMeta,
    PsychologicalMeta,
    SessionLevelMeta,
    SwingClusterMeta,
    VolumeDistributionMeta,
    VolumeProfileMeta,
    WickRejectionMeta,
)

from server.store.indicators import _ns_to_iso


# ---------------------------------------------------------------------------
# Detector protocol — structural typing for the registry
# ---------------------------------------------------------------------------


class DetectorProto(Protocol):
    def update(self, bar: Bar) -> None: ...

    def levels(self) -> list[KeyLevel]: ...


# ---------------------------------------------------------------------------
# Pydantic DTOs (wire format)
# ---------------------------------------------------------------------------


class EqualHighsLowsMetaDto(BaseModel):
    kind: Literal["equal_highs_lows"] = "equal_highs_lows"
    touch_prices: tuple[float, ...]
    side: Literal["high", "low"]
    touch_count: int


class WickRejectionMetaDto(BaseModel):
    kind: Literal["wick_rejection"] = "wick_rejection"
    rejection_count: int
    avg_wick_ratio: float
    side: Literal["high", "low"]
    touch_count: int


class AtrVolatilityMetaDto(BaseModel):
    kind: Literal["atr_volatility"] = "atr_volatility"
    atr_value: float
    multiplier: float
    anchor_price: float
    side: Literal["high", "low"]
    touch_count: int


class FibonacciMetaDto(BaseModel):
    kind: Literal["fibonacci"] = "fibonacci"
    ratio: float
    swing_high: float
    swing_low: float
    direction: Literal["retracement", "extension"]
    side: Literal["high", "low"]
    touch_count: int


class PivotPointMetaDto(BaseModel):
    kind: Literal["pivot_point"] = "pivot_point"
    variant: Literal["standard", "fibonacci", "camarilla", "woodie", "demark"]
    level_name: str
    period_high: float
    period_low: float
    period_close: float
    side: Literal["high", "low"]
    touch_count: int


class PsychologicalMetaDto(BaseModel):
    kind: Literal["psychological"] = "psychological"
    tier: Literal["major", "minor", "micro"]
    round_value: float
    side: Literal["high", "low"]
    touch_count: int


class VolumeProfileMetaDto(BaseModel):
    kind: Literal["volume_profile"] = "volume_profile"
    volume_concentration: float
    node_type: Literal["poc", "hvn", "lvn", "va_high", "va_low"]
    bin_volume: float
    side: Literal["high", "low"]
    touch_count: int


class VolumeDistributionMetaDto(BaseModel):
    kind: Literal["volume_distribution"] = "volume_distribution"
    context: Literal["consolidation", "peak", "trough", "range"]
    volume_concentration: float
    context_bar_count: int
    side: Literal["high", "low"]
    touch_count: int


class AnchoredVwapMetaDto(BaseModel):
    kind: Literal["anchored_vwap"] = "anchored_vwap"
    anchor_ts: int
    anchor_type: Literal["swing_high", "swing_low", "gap", "volume_spike"]
    cumulative_volume: float
    side: Literal["high", "low"]
    touch_count: int


class CvdMetaDto(BaseModel):
    kind: Literal["cvd"] = "cvd"
    cvd_value: float
    divergence: Literal["bullish", "bearish", "none"]
    side: Literal["high", "low"]
    touch_count: int


class SessionLevelMetaDto(BaseModel):
    kind: Literal["session_level"] = "session_level"
    session: Literal["asian", "london", "new_york", "custom"]
    role: Literal["high", "low"]
    session_date_iso: str
    side: Literal["high", "low"]
    touch_count: int


class PeriodicLevelMetaDto(BaseModel):
    kind: Literal["periodic_level"] = "periodic_level"
    period: Literal["daily", "weekly", "monthly"]
    role: Literal["high", "low"]
    period_start_iso: str
    side: Literal["high", "low"]
    touch_count: int


class OpeningRangeMetaDto(BaseModel):
    kind: Literal["opening_range"] = "opening_range"
    range_minutes: int
    role: Literal["high", "low"]
    side: Literal["high", "low"]
    touch_count: int


class MarketProfileMetaDto(BaseModel):
    kind: Literal["market_profile_tpo"] = "market_profile_tpo"
    tpo_count: int
    role: Literal["poc", "vah", "val"]
    total_tpo_periods: int
    side: Literal["high", "low"]
    touch_count: int


class SwingClusterMetaDto(BaseModel):
    kind: Literal["swing_cluster"] = "swing_cluster"
    cluster_radius: float
    pivot_indices: tuple[int, ...]
    side: Literal["high", "low"]
    touch_count: int


SourceMetaDto = Annotated[
    Union[
        EqualHighsLowsMetaDto,
        WickRejectionMetaDto,
        AtrVolatilityMetaDto,
        FibonacciMetaDto,
        PivotPointMetaDto,
        PsychologicalMetaDto,
        VolumeProfileMetaDto,
        VolumeDistributionMetaDto,
        AnchoredVwapMetaDto,
        CvdMetaDto,
        SessionLevelMetaDto,
        PeriodicLevelMetaDto,
        OpeningRangeMetaDto,
        MarketProfileMetaDto,
        SwingClusterMetaDto,
    ],
    Field(discriminator="kind"),
]


class KeyLevelDto(BaseModel):
    price: float
    strength: float
    start_ts: str
    end_ts: str | None
    source: Literal[
        "equal_highs_lows",
        "wick_rejection",
        "atr_volatility",
        "fib_retracement",
        "fib_extension",
        "pivot_standard",
        "pivot_fibonacci",
        "pivot_camarilla",
        "pivot_woodie",
        "pivot_demark",
        "psychological",
        "volume_profile",
        "volume_distribution",
        "anchored_vwap",
        "cvd",
        "session_level",
        "periodic_level",
        "opening_range",
        "market_profile_tpo",
        "swing_cluster",
    ]
    bounce_count: int
    zone_upper: float | None
    zone_lower: float | None
    meta: SourceMetaDto


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


# Default tier_steps for psychological levels — chosen to be reasonable for
# instruments priced ~100-2000 (e.g. metals, indices). Override via custom
# detector wiring if/when the route grows config support.
_DEFAULT_PSYCH_TIERS = {"major": 100.0, "minor": 50.0, "micro": 25.0}


DETECTOR_REGISTRY: dict[str, Callable[[], DetectorProto]] = {
    "equal_highs_lows": lambda: EqualHighsLowsDetector(),
    "wick_rejection": lambda: WickRejectionDetector(),
    "atr_volatility": lambda: AtrVolatilityDetector(),
    "fib_retracement": lambda: FibonacciRetracementDetector(),
    "fib_extension": lambda: FibonacciExtensionDetector(),
    "pivot_standard": lambda: PivotPointDetector(variant="standard"),
    "pivot_fibonacci": lambda: PivotPointDetector(variant="fibonacci"),
    "pivot_camarilla": lambda: PivotPointDetector(variant="camarilla"),
    "pivot_woodie": lambda: PivotPointDetector(variant="woodie"),
    "pivot_demark": lambda: PivotPointDetector(variant="demark"),
    "psychological": lambda: PsychologicalLevelDetector(
        tier_steps=_DEFAULT_PSYCH_TIERS,
    ),
    "volume_profile": lambda: VolumeProfileDetector(),
    "volume_distribution": lambda: VolumeDistributionDetector(),
    "anchored_vwap": lambda: AnchoredVwapDetector(),
    "cvd": lambda: CvdDetector(),
    "session_level": lambda: SessionLevelDetector(),
    "periodic_level": lambda: PeriodicLevelDetector(),
    "opening_range": lambda: OpeningRangeDetector(),
    "market_profile_tpo": lambda: MarketProfileDetector(),
    "swing_cluster": lambda: SwingClusterDetector(),
}


DETECTOR_META: list[dict[str, str]] = [
    {"id": "equal_highs_lows", "label": "Equal Highs/Lows", "color": "#5470c6"},
    {"id": "wick_rejection", "label": "Wick Rejection", "color": "#ee6666"},
    {"id": "atr_volatility", "label": "ATR Volatility", "color": "#fac858"},
    {"id": "fib_retracement", "label": "Fib Retracement", "color": "#91cc75"},
    {"id": "fib_extension", "label": "Fib Extension", "color": "#91cc75"},
    {"id": "pivot_standard", "label": "Pivot (Standard)", "color": "#73c0de"},
    {"id": "pivot_fibonacci", "label": "Pivot (Fibonacci)", "color": "#73c0de"},
    {"id": "pivot_camarilla", "label": "Pivot (Camarilla)", "color": "#73c0de"},
    {"id": "pivot_woodie", "label": "Pivot (Woodie)", "color": "#73c0de"},
    {"id": "pivot_demark", "label": "Pivot (DeMark)", "color": "#73c0de"},
    {"id": "psychological", "label": "Psychological", "color": "#9a60b4"},
    {"id": "volume_profile", "label": "Volume Profile", "color": "#ea7ccc"},
    {"id": "volume_distribution", "label": "Volume Distribution", "color": "#3ba272"},
    {"id": "anchored_vwap", "label": "Anchored VWAP", "color": "#fc8452"},
    {"id": "cvd", "label": "CVD", "color": "#27727b"},
    {"id": "session_level", "label": "Session Levels", "color": "#3d5499"},
    {"id": "periodic_level", "label": "Periodic Levels", "color": "#d48265"},
    {"id": "opening_range", "label": "Opening Range", "color": "#759aa0"},
    {"id": "market_profile_tpo", "label": "Market Profile (TPO)", "color": "#c1232b"},
    {"id": "swing_cluster", "label": "Swing Cluster", "color": "#b5c334"},
]


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _meta_to_dto(meta: object) -> SourceMetaDto:
    """Convert a frozen-dataclass SourceMeta to its Pydantic DTO equivalent."""
    if isinstance(meta, EqualHighsLowsMeta):
        return EqualHighsLowsMetaDto(
            touch_prices=tuple(meta.touch_prices),
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, WickRejectionMeta):
        return WickRejectionMetaDto(
            rejection_count=meta.rejection_count,
            avg_wick_ratio=meta.avg_wick_ratio,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, AtrVolatilityMeta):
        return AtrVolatilityMetaDto(
            atr_value=meta.atr_value,
            multiplier=meta.multiplier,
            anchor_price=meta.anchor_price,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, FibonacciMeta):
        return FibonacciMetaDto(
            ratio=meta.ratio,
            swing_high=meta.swing_high,
            swing_low=meta.swing_low,
            direction=meta.direction,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, PivotPointMeta):
        return PivotPointMetaDto(
            variant=meta.variant,
            level_name=meta.level_name,
            period_high=meta.period_high,
            period_low=meta.period_low,
            period_close=meta.period_close,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, PsychologicalMeta):
        return PsychologicalMetaDto(
            tier=meta.tier,
            round_value=meta.round_value,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, VolumeProfileMeta):
        return VolumeProfileMetaDto(
            volume_concentration=meta.volume_concentration,
            node_type=meta.node_type,
            bin_volume=meta.bin_volume,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, VolumeDistributionMeta):
        return VolumeDistributionMetaDto(
            context=meta.context,
            volume_concentration=meta.volume_concentration,
            context_bar_count=meta.context_bar_count,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, AnchoredVwapMeta):
        return AnchoredVwapMetaDto(
            anchor_ts=meta.anchor_ts,
            anchor_type=meta.anchor_type,
            cumulative_volume=meta.cumulative_volume,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, CvdMeta):
        return CvdMetaDto(
            cvd_value=meta.cvd_value,
            divergence=meta.divergence,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, SessionLevelMeta):
        return SessionLevelMetaDto(
            session=meta.session,
            role=meta.role,
            session_date_iso=meta.session_date_iso,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, PeriodicLevelMeta):
        return PeriodicLevelMetaDto(
            period=meta.period,
            role=meta.role,
            period_start_iso=meta.period_start_iso,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, OpeningRangeMeta):
        return OpeningRangeMetaDto(
            range_minutes=meta.range_minutes,
            role=meta.role,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, MarketProfileMeta):
        return MarketProfileMetaDto(
            tpo_count=meta.tpo_count,
            role=meta.role,
            total_tpo_periods=meta.total_tpo_periods,
            side=meta.side,
            touch_count=meta.touch_count,
        )
    if isinstance(meta, SwingClusterMeta):
        return SwingClusterMetaDto(
            cluster_radius=meta.cluster_radius,
            pivot_indices=tuple(meta.pivot_indices),
            side=meta.side,
            touch_count=meta.touch_count,
        )
    raise TypeError(f"Unsupported meta type: {type(meta).__name__}")


def _to_dto(level: KeyLevel) -> KeyLevelDto:
    return KeyLevelDto(
        price=level.price,
        strength=level.strength,
        start_ts=_ns_to_iso(level.start_ts),
        end_ts=_ns_to_iso(level.end_ts) if level.end_ts is not None else None,
        source=level.source,  # type: ignore[arg-type]
        bounce_count=level.bounce_count,
        zone_upper=level.zone_upper,
        zone_lower=level.zone_lower,
        meta=_meta_to_dto(level.meta),
    )


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------


def compute_key_levels(detector_id: str, bars: list[Bar]) -> list[KeyLevelDto]:
    """Run a fresh detector instance over bars and return DTOs for its levels."""
    detector = DETECTOR_REGISTRY[detector_id]()
    for bar in bars:
        detector.update(bar)
    return [_to_dto(lvl) for lvl in detector.levels()]
