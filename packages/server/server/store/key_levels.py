"""Key Level detector registry, DTOs, and compute path.

Lifecycle-tracked KeyLevels are produced by detectors and exposed via FastAPI
as Pydantic DTOs with a discriminated ``meta`` union — additive on both sides
as more detectors migrate to the event-based lifecycle model.
"""

from __future__ import annotations

from typing import Annotated, Callable, Literal, Protocol, Union

from pydantic import BaseModel, Field

from nautilus_trader.model.data import Bar

from indicators.key_levels.detectors.atr_volatility import AtrVolatilityDetector
from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.detectors.fibonacci import (
    FibonacciExtensionDetector,
    FibonacciRetracementDetector,
)
from indicators.key_levels.detectors.pivot_points import PivotPointDetector
from indicators.key_levels.detectors.psychological import PsychologicalLevelDetector
from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from indicators.key_levels.model import (
    AtrVolatilityMeta,
    EqualHighsLowsMeta,
    FibonacciMeta,
    KeyLevel,
    PivotPointMeta,
    PsychologicalMeta,
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


SourceMetaDto = Annotated[
    Union[
        EqualHighsLowsMetaDto,
        WickRejectionMetaDto,
        AtrVolatilityMetaDto,
        FibonacciMetaDto,
        PivotPointMetaDto,
        PsychologicalMetaDto,
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
