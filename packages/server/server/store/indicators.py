"""Indicator registry and compute functions.

Typed registry using Protocols, frozen dataclasses, and callable update
strategies for type-safe integration with NautilusTrader indicators.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Literal, Protocol

from nautilus_trader.indicators import (
    AverageTrueRange,
    BollingerBands,
    DonchianChannel,
    ExponentialMovingAverage,
    HullMovingAverage,
    MovingAverageConvergenceDivergence,
    RelativeStrengthIndex,
    SimpleMovingAverage,
    Stochastics,
)
from nautilus_trader.model.data import Bar

from indicators.zigzag import ZigZagIndicator


# ---------------------------------------------------------------------------
# Protocols – structural types for Cython indicator classes
# ---------------------------------------------------------------------------


class IndicatorProto(Protocol):
    @property
    def initialized(self) -> bool: ...

    def update_raw(self, *args: float) -> None: ...


# ---------------------------------------------------------------------------
# Typed update strategies (replace string dispatch)
# ---------------------------------------------------------------------------

# Using IndicatorProto here rather than Any so the update callable contract
# is fully typed. Cython indicator classes satisfy this Protocol structurally
# at runtime, even though static analysers may not verify it.
UpdateFn = Callable[[IndicatorProto, Bar], None]


def update_close(indicator: IndicatorProto, bar: Bar) -> None:
    indicator.update_raw(float(bar.close))


def update_hlc(indicator: IndicatorProto, bar: Bar) -> None:
    indicator.update_raw(float(bar.high), float(bar.low), float(bar.close))


def update_hl(indicator: IndicatorProto, bar: Bar) -> None:
    indicator.update_raw(float(bar.high), float(bar.low))


def update_bar(indicator: IndicatorProto, bar: Bar) -> None:
    indicator.handle_bar(bar)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Typed config and result dataclasses
# ---------------------------------------------------------------------------

Display = Literal["overlay", "panel"]


@dataclass(frozen=True)
class IndicatorConfig:
    # Cython indicator classes satisfy IndicatorProto structurally at runtime
    # but static analysers cannot verify Cython .pxd declarations.
    indicator_class: type[IndicatorProto]
    params: tuple[int | float, ...]
    outputs: tuple[str, ...]
    display: Display
    label: str
    update: UpdateFn
    kwargs: dict[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class IndicatorMeta:
    id: str
    label: str
    display: Display
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class IndicatorResult:
    id: str
    label: str
    display: Display
    outputs: dict[str, list[float | None]]
    datetime: list[str]


# ---------------------------------------------------------------------------
# Registry – direct class refs, typed update fns, no string dispatch
# ---------------------------------------------------------------------------

INDICATOR_REGISTRY: dict[str, IndicatorConfig] = {
    "SMA_20": IndicatorConfig(
        indicator_class=SimpleMovingAverage,
        params=(20,),
        outputs=("value",),
        display="overlay",
        label="SMA(20)",
        update=update_close,
    ),
    "SMA_50": IndicatorConfig(
        indicator_class=SimpleMovingAverage,
        params=(50,),
        outputs=("value",),
        display="overlay",
        label="SMA(50)",
        update=update_close,
    ),
    "EMA_20": IndicatorConfig(
        indicator_class=ExponentialMovingAverage,
        params=(20,),
        outputs=("value",),
        display="overlay",
        label="EMA(20)",
        update=update_close,
    ),
    "HMA_20": IndicatorConfig(
        indicator_class=HullMovingAverage,
        params=(20,),
        outputs=("value",),
        display="overlay",
        label="HMA(20)",
        update=update_close,
    ),
    "BollingerBands_20": IndicatorConfig(
        indicator_class=BollingerBands,
        params=(20, 2.0),
        outputs=("upper", "middle", "lower"),
        display="overlay",
        label="BB(20,2)",
        update=update_hlc,
    ),
    "DonchianChannel_20": IndicatorConfig(
        indicator_class=DonchianChannel,
        params=(20,),
        outputs=("upper", "middle", "lower"),
        display="overlay",
        label="DC(20)",
        update=update_hl,
    ),
    "RSI_14": IndicatorConfig(
        indicator_class=RelativeStrengthIndex,
        params=(14,),
        outputs=("value",),
        display="panel",
        label="RSI(14)",
        update=update_close,
    ),
    "MACD_12_26_9": IndicatorConfig(
        indicator_class=MovingAverageConvergenceDivergence,
        params=(),
        outputs=("value",),
        display="panel",
        label="MACD(12,26)",
        update=update_close,
        kwargs={"fast_period": 12, "slow_period": 26},
    ),
    "ATR_14": IndicatorConfig(
        indicator_class=AverageTrueRange,
        params=(14,),
        outputs=("value",),
        display="panel",
        label="ATR(14)",
        update=update_hlc,
    ),
    "Stochastics_14_3": IndicatorConfig(
        indicator_class=Stochastics,
        params=(14, 3),
        outputs=("value_k", "value_d"),
        display="panel",
        label="Stoch(14,3)",
        update=update_hlc,
    ),
    "ZigZag_5pct": IndicatorConfig(
        indicator_class=ZigZagIndicator,  # type: ignore[arg-type]
        params=(0.05,),
        outputs=("zigzag",),
        display="overlay",
        label="ZigZag(5%)",
        update=update_bar,
    ),
    "ZigZag_3pct": IndicatorConfig(
        indicator_class=ZigZagIndicator,  # type: ignore[arg-type]
        params=(0.03,),
        outputs=("zigzag",),
        display="overlay",
        label="ZigZag(3%)",
        update=update_bar,
    ),
    "ZigZag_01pct": IndicatorConfig(
        indicator_class=ZigZagIndicator,  # type: ignore[arg-type]
        params=(0.001,),
        outputs=("zigzag",),
        display="overlay",
        label="ZigZag(0.1%)",
        update=update_bar,
    ),
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def _ns_to_iso(ns: int) -> str:
    """Convert nanosecond timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


def list_available_indicators() -> list[IndicatorMeta]:
    """Return metadata for all registered indicators."""
    return [
        IndicatorMeta(
            id=indicator_id,
            label=config.label,
            display=config.display,
            outputs=config.outputs,
        )
        for indicator_id, config in INDICATOR_REGISTRY.items()
    ]


def _compute_zigzag(indicator_id: str, bars: list[Bar]) -> IndicatorResult:
    """Compute a ZigZag indicator, producing a sparse series for diagonal lines.

    Values are emitted at the bars where the swing extremes occurred (not where
    the reversal was confirmed), so the zigzag line aligns with candle highs/lows.
    """
    config = INDICATOR_REGISTRY[indicator_id]
    indicator = config.indicator_class(*config.params, **config.kwargs)

    # Build timestamp -> bar index map for placing pivots at the correct bar
    ts_to_idx: dict[int, int] = {}
    datetimes: list[str] = []

    for i, bar in enumerate(bars):
        ts_to_idx[bar.ts_init] = i
        config.update(indicator, bar)
        datetimes.append(_ns_to_iso(bar.ts_event))

    # Build sparse zigzag line using pivot timestamps to find the correct bar
    zigzag: list[float | None] = [None] * len(bars)

    for pivot in indicator.pivots:  # type: ignore[attr-defined]
        bar_idx = ts_to_idx.get(pivot.timestamp)
        if bar_idx is not None:
            zigzag[bar_idx] = pivot.price

    # Add tentative (current) extreme at the bar where it occurred
    if indicator.initialized and len(bars) > 0:  # type: ignore[attr-defined]
        tentative_idx = ts_to_idx.get(
            indicator.tentative_timestamp  # type: ignore[attr-defined]
        )
        if tentative_idx is not None:
            zigzag[tentative_idx] = float(
                indicator.tentative_price  # type: ignore[attr-defined]
            )

    return IndicatorResult(
        id=indicator_id,
        label=config.label,
        display=config.display,
        outputs={"zigzag": zigzag},
        datetime=datetimes,
    )


_ZIGZAG_IDS = frozenset({"ZigZag_5pct", "ZigZag_3pct", "ZigZag_01pct"})


def compute_indicator(indicator_id: str, bars: list[Bar]) -> IndicatorResult:
    """Instantiate an indicator, feed it bars, and collect output series.

    Args:
        indicator_id: Key into INDICATOR_REGISTRY (e.g. "SMA_20").
        bars: List of nautilus_trader Bar objects.

    Returns:
        IndicatorResult with typed fields.
    """
    if indicator_id in _ZIGZAG_IDS:
        return _compute_zigzag(indicator_id, bars)

    config = INDICATOR_REGISTRY[indicator_id]
    indicator = config.indicator_class(*config.params, **config.kwargs)

    outputs: dict[str, list[float | None]] = {f: [] for f in config.outputs}
    datetimes: list[str] = []

    for bar in bars:
        config.update(indicator, bar)
        datetimes.append(_ns_to_iso(bar.ts_event))

        if indicator.initialized:
            for f in config.outputs:
                outputs[f].append(float(getattr(indicator, f)))
        else:
            for f in config.outputs:
                outputs[f].append(None)

    return IndicatorResult(
        id=indicator_id,
        label=config.label,
        display=config.display,
        outputs=outputs,
        datetime=datetimes,
    )
