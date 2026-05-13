"""Indicator type registry and compute functions.

Parameterized indicator types using Protocols, frozen dataclasses, and callable
update strategies for type-safe integration with NautilusTrader indicators.

Each `IndicatorType` carries a `params` schema so the UI can render a config
form; `build_indicator_from_instance` validates params and instantiates the
indicator class.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Protocol


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
# Display type alias
# ---------------------------------------------------------------------------

Display = Literal["overlay", "panel"]


# ---------------------------------------------------------------------------
# Parameter schema and indicator type dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParamSchema:
    """Schema definition for a single indicator parameter."""

    name: str
    type: Literal["int", "float"]
    default: int | float
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    label: str | None = None  # display label; defaults to name if None


@dataclass(frozen=True)
class IndicatorType:
    """A parameterized indicator type entry in the registry."""

    type: str
    label_template: str  # e.g. "SMA({period})" — formatted with params
    display: Display
    outputs: tuple[str, ...]
    params: tuple[ParamSchema, ...]
    factory: Callable[[dict[str, Any]], IndicatorProto]
    update: UpdateFn


# ---------------------------------------------------------------------------
# Result dataclass (kept for route layer compatibility)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorResult:
    id: str
    label: str
    display: Display
    outputs: dict[str, list[float | None]]
    datetime: list[str]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ParamValidationError(ValueError):
    """Raised when indicator params fail schema validation."""


# ---------------------------------------------------------------------------
# Registry – INDICATOR_TYPES keyed by indicator type string
# ---------------------------------------------------------------------------

INDICATOR_TYPES: dict[str, IndicatorType] = {
    "SMA": IndicatorType(
        type="SMA",
        label_template="SMA({period})",
        display="overlay",
        outputs=("value",),
        params=(
            ParamSchema(name="period", type="int", default=20, min=2, max=500),
        ),
        factory=lambda p: SimpleMovingAverage(period=p["period"]),
        update=update_close,
    ),
    "EMA": IndicatorType(
        type="EMA",
        label_template="EMA({period})",
        display="overlay",
        outputs=("value",),
        params=(
            ParamSchema(name="period", type="int", default=20, min=2, max=500),
        ),
        factory=lambda p: ExponentialMovingAverage(period=p["period"]),
        update=update_close,
    ),
    "HMA": IndicatorType(
        type="HMA",
        label_template="HMA({period})",
        display="overlay",
        outputs=("value",),
        params=(
            ParamSchema(name="period", type="int", default=20, min=2, max=500),
        ),
        factory=lambda p: HullMovingAverage(period=p["period"]),
        update=update_close,
    ),
    "BB": IndicatorType(
        type="BB",
        label_template="BB({period},{std_dev})",
        display="overlay",
        outputs=("upper", "middle", "lower"),
        params=(
            ParamSchema(name="period", type="int", default=20, min=2, max=500),
            ParamSchema(
                name="std_dev",
                type="float",
                default=2.0,
                min=0.1,
                max=10.0,
                step=0.1,
            ),
        ),
        factory=lambda p: BollingerBands(period=p["period"], k=p["std_dev"]),
        update=update_hlc,
    ),
    "Donchian": IndicatorType(
        type="Donchian",
        label_template="DC({period})",
        display="overlay",
        outputs=("upper", "middle", "lower"),
        params=(
            ParamSchema(name="period", type="int", default=20, min=2, max=500),
        ),
        factory=lambda p: DonchianChannel(period=p["period"]),
        update=update_hl,
    ),
    "RSI": IndicatorType(
        type="RSI",
        label_template="RSI({period})",
        display="panel",
        outputs=("value",),
        params=(
            ParamSchema(name="period", type="int", default=14, min=2, max=100),
        ),
        factory=lambda p: RelativeStrengthIndex(period=p["period"]),
        update=update_close,
    ),
    "MACD": IndicatorType(
        type="MACD",
        label_template="MACD({fast_period},{slow_period})",
        display="panel",
        outputs=("value",),
        params=(
            ParamSchema(
                name="fast_period",
                type="int",
                default=12,
                min=2,
                max=200,
                label="Fast Period",
            ),
            ParamSchema(
                name="slow_period",
                type="int",
                default=26,
                min=2,
                max=500,
                label="Slow Period",
            ),
        ),
        # NautilusTrader's MACD only accepts fast_period and slow_period;
        # signal_period is not supported by this indicator class.
        factory=lambda p: MovingAverageConvergenceDivergence(
            fast_period=p["fast_period"],
            slow_period=p["slow_period"],
        ),
        update=update_close,
    ),
    "ATR": IndicatorType(
        type="ATR",
        label_template="ATR({period})",
        display="panel",
        outputs=("value",),
        params=(
            ParamSchema(name="period", type="int", default=14, min=1, max=200),
        ),
        factory=lambda p: AverageTrueRange(period=p["period"]),
        update=update_hlc,
    ),
    "Stochastics": IndicatorType(
        type="Stochastics",
        label_template="Stoch({period_k},{period_d})",
        display="panel",
        outputs=("value_k", "value_d"),
        params=(
            ParamSchema(
                name="period_k",
                type="int",
                default=14,
                min=1,
                max=200,
                label="%K Period",
            ),
            ParamSchema(
                name="period_d",
                type="int",
                default=3,
                min=1,
                max=200,
                label="%D Period",
            ),
        ),
        factory=lambda p: Stochastics(period_k=p["period_k"], period_d=p["period_d"]),
        update=update_hlc,
    ),
    "ZigZag": IndicatorType(
        type="ZigZag",
        label_template="ZigZag({threshold})",
        display="overlay",
        outputs=("zigzag",),
        params=(
            ParamSchema(
                name="threshold",
                type="float",
                default=0.05,
                min=0.001,
                max=0.5,
                step=0.001,
                label="Threshold",
            ),
        ),
        factory=lambda p: ZigZagIndicator(p["threshold"]),  # type: ignore[arg-type]
        update=update_bar,
    ),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def format_label(t: IndicatorType, params: dict[str, Any]) -> str:
    """Format an indicator label by interpolating params into the label template."""
    return t.label_template.format(**params)


def build_indicator_from_instance(
    type_name: str,
    params: dict[str, Any],
) -> IndicatorProto:
    """Validate params against schema and instantiate the indicator.

    Args:
        type_name: Key into INDICATOR_TYPES (e.g. "SMA").
        params: Parameter dict (e.g. {"period": 20}).

    Returns:
        An instantiated indicator satisfying IndicatorProto.

    Raises:
        KeyError: If type_name is not in INDICATOR_TYPES.
        ParamValidationError: If any param fails schema validation.
    """
    indicator_type = INDICATOR_TYPES[type_name]

    for schema in indicator_type.params:
        if schema.name not in params:
            raise ParamValidationError(
                f"Missing required param '{schema.name}' for indicator '{type_name}'"
            )

        value = params[schema.name]

        # Type check
        if schema.type == "int":
            if not isinstance(value, int):
                raise ParamValidationError(
                    f"Param '{schema.name}' for '{type_name}' must be an int, "
                    f"got {type(value).__name__}: {value!r}"
                )
        elif schema.type == "float":
            if not isinstance(value, (int, float)):
                raise ParamValidationError(
                    f"Param '{schema.name}' for '{type_name}' must be a float, "
                    f"got {type(value).__name__}: {value!r}"
                )

        # Range checks
        if schema.min is not None and value < schema.min:
            raise ParamValidationError(
                f"Param '{schema.name}' for '{type_name}' must be >= {schema.min}, "
                f"got {value}"
            )
        if schema.max is not None and value > schema.max:
            raise ParamValidationError(
                f"Param '{schema.name}' for '{type_name}' must be <= {schema.max}, "
                f"got {value}"
            )

    return indicator_type.factory(params)


# ---------------------------------------------------------------------------
# Private compute helpers
# ---------------------------------------------------------------------------


def _ns_to_iso(ns: int) -> str:
    """Convert nanosecond timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


def _compute_zigzag(
    instance_id: str,
    label: str,
    indicator: IndicatorProto,
    update: UpdateFn,
    bars: list[Bar],
) -> IndicatorResult:
    """Compute a ZigZag indicator, producing a sparse series for diagonal lines.

    Values are emitted at the bars where the swing extremes occurred (not where
    the reversal was confirmed), so the zigzag line aligns with candle highs/lows.
    """
    # Build timestamp -> bar index map for placing pivots at the correct bar
    ts_to_idx: dict[int, int] = {}
    datetimes: list[str] = []

    for i, bar in enumerate(bars):
        ts_to_idx[bar.ts_init] = i
        update(indicator, bar)
        datetimes.append(_ns_to_iso(bar.ts_event))

    # Build sparse zigzag line using pivot timestamps to find the correct bar
    zigzag: list[float | None] = [None] * len(bars)

    for pivot in indicator.pivots:  # type: ignore[attr-defined]
        bar_idx = ts_to_idx.get(pivot.timestamp)
        if bar_idx is not None:
            zigzag[bar_idx] = pivot.price

    # Add tentative (current) extreme at the bar where it occurred
    if indicator.initialized and len(bars) > 0:
        tentative_idx = ts_to_idx.get(
            indicator.tentative_timestamp  # type: ignore[attr-defined]
        )
        if tentative_idx is not None:
            zigzag[tentative_idx] = float(
                indicator.tentative_price  # type: ignore[attr-defined]
            )

    return IndicatorResult(
        id=instance_id,
        label=label,
        display="overlay",
        outputs={"zigzag": zigzag},
        datetime=datetimes,
    )


def compute_indicator_instance(
    instance_id: str,
    type_name: str,
    params: dict[str, Any],
    bars: list[Bar],
) -> IndicatorResult:
    """Validate params, instantiate an indicator, feed it bars, collect output series.

    Args:
        instance_id: Caller-supplied UUID for this instance (used as result id).
        type_name: Key into INDICATOR_TYPES (e.g. "SMA").
        params: Parameter dict validated against schema.
        bars: List of nautilus_trader Bar objects.

    Returns:
        IndicatorResult with typed fields.

    Raises:
        KeyError: If type_name is not in INDICATOR_TYPES.
        ParamValidationError: If any param fails schema validation.
    """
    indicator_type = INDICATOR_TYPES[type_name]
    indicator = build_indicator_from_instance(type_name, params)
    label = format_label(indicator_type, params)

    if indicator_type.type == "ZigZag":
        return _compute_zigzag(
            instance_id, label, indicator, indicator_type.update, bars
        )

    outputs: dict[str, list[float | None]] = {f: [] for f in indicator_type.outputs}
    datetimes: list[str] = []

    for bar in bars:
        indicator_type.update(indicator, bar)
        datetimes.append(_ns_to_iso(bar.ts_event))

        if indicator.initialized:
            for f in indicator_type.outputs:
                outputs[f].append(float(getattr(indicator, f)))
        else:
            for f in indicator_type.outputs:
                outputs[f].append(None)

    return IndicatorResult(
        id=instance_id,
        label=label,
        display=indicator_type.display,
        outputs=outputs,
        datetime=datetimes,
    )
