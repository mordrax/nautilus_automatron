"""Indicator registry and compute functions.

Pure functions for instantiating NautilusTrader indicators,
feeding them bar data, and collecting output series.
"""

from datetime import datetime, timezone

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


INDICATOR_REGISTRY: dict[str, dict] = {
    "SMA_20": {
        "class_name": "SimpleMovingAverage",
        "params": [20],
        "outputs": ["value"],
        "display": "overlay",
        "label": "SMA(20)",
        "update": "close",
    },
    "SMA_50": {
        "class_name": "SimpleMovingAverage",
        "params": [50],
        "outputs": ["value"],
        "display": "overlay",
        "label": "SMA(50)",
        "update": "close",
    },
    "EMA_20": {
        "class_name": "ExponentialMovingAverage",
        "params": [20],
        "outputs": ["value"],
        "display": "overlay",
        "label": "EMA(20)",
        "update": "close",
    },
    "HMA_20": {
        "class_name": "HullMovingAverage",
        "params": [20],
        "outputs": ["value"],
        "display": "overlay",
        "label": "HMA(20)",
        "update": "close",
    },
    "BollingerBands_20": {
        "class_name": "BollingerBands",
        "params": [20, 2.0],
        "outputs": ["upper", "middle", "lower"],
        "display": "overlay",
        "label": "BB(20,2)",
        "update": "hlc",
    },
    "DonchianChannel_20": {
        "class_name": "DonchianChannel",
        "params": [20],
        "outputs": ["upper", "middle", "lower"],
        "display": "overlay",
        "label": "DC(20)",
        "update": "hl",
    },
    "RSI_14": {
        "class_name": "RelativeStrengthIndex",
        "params": [14],
        "outputs": ["value"],
        "display": "panel",
        "label": "RSI(14)",
        "update": "close",
    },
    "MACD_12_26_9": {
        "class_name": "MovingAverageConvergenceDivergence",
        "params": [],
        "kwargs": {"fast_period": 12, "slow_period": 26},
        "outputs": ["value"],
        "display": "panel",
        "label": "MACD(12,26)",
        "update": "close",
    },
    "ATR_14": {
        "class_name": "AverageTrueRange",
        "params": [14],
        "outputs": ["value"],
        "display": "panel",
        "label": "ATR(14)",
        "update": "hlc",
    },
    "Stochastics_14_3": {
        "class_name": "Stochastics",
        "params": [14, 3],
        "outputs": ["value_k", "value_d"],
        "display": "panel",
        "label": "Stoch(14,3)",
        "update": "hlc",
    },
}

_CLASS_MAP = {
    "SimpleMovingAverage": SimpleMovingAverage,
    "ExponentialMovingAverage": ExponentialMovingAverage,
    "HullMovingAverage": HullMovingAverage,
    "BollingerBands": BollingerBands,
    "DonchianChannel": DonchianChannel,
    "RelativeStrengthIndex": RelativeStrengthIndex,
    "MovingAverageConvergenceDivergence": MovingAverageConvergenceDivergence,
    "AverageTrueRange": AverageTrueRange,
    "Stochastics": Stochastics,
}


def _ns_to_iso(ns: int) -> str:
    """Convert nanosecond timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


def list_available_indicators() -> list[dict]:
    """Return metadata for all registered indicators."""
    return [
        {
            "id": indicator_id,
            "label": entry["label"],
            "display": entry["display"],
            "outputs": entry["outputs"],
        }
        for indicator_id, entry in INDICATOR_REGISTRY.items()
    ]


def compute_indicator(indicator_id: str, bars: list) -> dict:
    """Instantiate an indicator, feed it bars, and collect output series.

    Args:
        indicator_id: Key into INDICATOR_REGISTRY (e.g. "SMA_20").
        bars: List of nautilus_trader.model.data.Bar objects.

    Returns:
        Dict with id, label, display, outputs (dict of field -> list[float|None]),
        and datetime (list of ISO strings).
    """
    entry = INDICATOR_REGISTRY[indicator_id]
    cls = _CLASS_MAP[entry["class_name"]]
    indicator = cls(*entry["params"], **entry.get("kwargs", {}))

    output_fields = entry["outputs"]
    outputs: dict[str, list[float | None]] = {field: [] for field in output_fields}
    datetimes: list[str] = []

    update_mode = entry["update"]

    for bar in bars:
        if update_mode == "close":
            indicator.update_raw(float(bar.close))
        elif update_mode == "hlc":
            indicator.update_raw(float(bar.high), float(bar.low), float(bar.close))
        elif update_mode == "hl":
            indicator.update_raw(float(bar.high), float(bar.low))

        datetimes.append(_ns_to_iso(bar.ts_event))

        if indicator.initialized:
            for field in output_fields:
                outputs[field].append(float(getattr(indicator, field)))
        else:
            for field in output_fields:
                outputs[field].append(None)

    return {
        "id": indicator_id,
        "label": entry["label"],
        "display": entry["display"],
        "outputs": outputs,
        "datetime": datetimes,
    }
