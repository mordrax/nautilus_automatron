"""Key Level detector registry, DTOs, and compute path.

Lifecycle-tracked KeyLevels are produced by detectors (currently only
``EqualHighsLowsDetector``) and exposed via FastAPI as Pydantic DTOs with a
discriminated ``meta`` union — room to grow as more detectors migrate to the
event-based lifecycle model.
"""

from __future__ import annotations

from typing import Annotated, Callable, Literal, Protocol, Union

from pydantic import BaseModel, Field

from nautilus_trader.model.data import Bar

from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.model import EqualHighsLowsMeta, KeyLevel

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


SourceMetaDto = Annotated[
    Union[EqualHighsLowsMetaDto],
    Field(discriminator="kind"),
]


class KeyLevelDto(BaseModel):
    price: float
    strength: float
    start_ts: str
    end_ts: str | None
    source: Literal["equal_highs_lows"]
    bounce_count: int
    zone_upper: float | None
    zone_lower: float | None
    meta: SourceMetaDto


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


DETECTOR_REGISTRY: dict[str, Callable[[], DetectorProto]] = {
    "equal_highs_lows": lambda: EqualHighsLowsDetector(),
}


DETECTOR_META: list[dict[str, str]] = [
    {"id": "equal_highs_lows", "label": "Equal Highs/Lows", "color": "#5470c6"},
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
