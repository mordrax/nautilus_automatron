"""PivotPointDetector -- calculate key levels from prior period OHLC data.

Supports five formula variants: standard, fibonacci, camarilla, woodie, demark.
A "period" is defined by *period_bars* consecutive bars.  When a period
completes, pivot levels are recalculated from that period's OHLC.
"""

from __future__ import annotations

from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PivotPointMeta
from indicators.key_levels.shared.atr import StreamingAtr

PivotVariant = Literal["standard", "fibonacci", "camarilla", "woodie", "demark"]

# Strength values by level tier
_STRENGTH: dict[str, float] = {
    "PP": 1.0,
    "R1": 0.8, "S1": 0.8,
    "R2": 0.6, "S2": 0.6,
    "R3": 0.4, "S3": 0.4,
    "R4": 0.3, "S4": 0.3,
}


def _compute_standard(h: float, lo: float, c: float) -> list[tuple[str, float]]:
    pp = (h + lo + c) / 3
    return [
        ("PP", pp),
        ("R1", 2 * pp - lo),
        ("S1", 2 * pp - h),
        ("R2", pp + (h - lo)),
        ("S2", pp - (h - lo)),
    ]


def _compute_fibonacci(h: float, lo: float, c: float) -> list[tuple[str, float]]:
    pp = (h + lo + c) / 3
    r = h - lo
    return [
        ("PP", pp),
        ("R1", pp + 0.382 * r),
        ("R2", pp + 0.618 * r),
        ("R3", pp + 1.0 * r),
        ("S1", pp - 0.382 * r),
        ("S2", pp - 0.618 * r),
        ("S3", pp - 1.0 * r),
    ]


def _compute_camarilla(h: float, lo: float, c: float) -> list[tuple[str, float]]:
    r = h - lo
    return [
        ("PP", (h + lo + c) / 3),
        ("R1", c + r * 1.1 / 12),
        ("R2", c + r * 1.1 / 6),
        ("R3", c + r * 1.1 / 4),
        ("R4", c + r * 1.1 / 2),
        ("S1", c - r * 1.1 / 12),
        ("S2", c - r * 1.1 / 6),
        ("S3", c - r * 1.1 / 4),
        ("S4", c - r * 1.1 / 2),
    ]


def _compute_woodie(h: float, lo: float, c: float) -> list[tuple[str, float]]:
    pp = (h + lo + 2 * c) / 4
    return [
        ("PP", pp),
        ("R1", 2 * pp - lo),
        ("S1", 2 * pp - h),
        ("R2", pp + (h - lo)),
        ("S2", pp - (h - lo)),
    ]


def _compute_demark(
    h: float, lo: float, c: float, o: float,
) -> list[tuple[str, float]]:
    if c < o:
        x = h + 2 * lo + c
    elif c > o:
        x = 2 * h + lo + c
    else:
        x = h + lo + 2 * c
    pp = x / 4
    return [
        ("PP", pp),
        ("R1", x / 2 - lo),
        ("S1", x / 2 - h),
    ]


_COMPUTE: dict[PivotVariant, object] = {
    "standard": _compute_standard,
    "fibonacci": _compute_fibonacci,
    "camarilla": _compute_camarilla,
    "woodie": _compute_woodie,
    # demark handled separately (needs open)
}


class PivotPointDetector:
    """Detects key levels using pivot point formulas from prior period OHLC.

    Args:
        variant: Which formula to use.
        period_bars: Number of bars per period (e.g., 24 for daily pivots from 1H bars).
        atr_period: ATR period for zone width. Default 14.
    """

    def __init__(
        self,
        variant: PivotVariant = "standard",
        period_bars: int = 24,
        atr_period: int = 14,
    ) -> None:
        self._variant = variant
        self._period_bars = period_bars
        self._atr = StreamingAtr(period=atr_period)

        # Current accumulating period
        self._bar_count: int = 0
        self._period_high: float = float("-inf")
        self._period_low: float = float("inf")
        self._period_open: float = 0.0
        self._period_close: float = 0.0
        self._period_last_ts: int = 0

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return f"pivot_{self._variant}"

    @property
    def warmup_bars(self) -> int:
        return self._period_bars

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        open_ = float(bar.open)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        # Accumulate period OHLC
        if self._bar_count == 0:
            self._period_open = open_
            self._period_high = high
            self._period_low = low
        else:
            self._period_high = max(self._period_high, high)
            self._period_low = min(self._period_low, low)

        self._period_close = close
        self._period_last_ts = ts
        self._bar_count += 1

        # Period complete
        if self._bar_count >= self._period_bars:
            self._compute_levels()
            # Reset accumulator
            self._bar_count = 0
            self._period_high = float("-inf")
            self._period_low = float("inf")
            self._period_open = 0.0
            self._period_close = 0.0

    def _compute_levels(self) -> None:
        h = self._period_high
        lo = self._period_low
        c = self._period_close
        o = self._period_open
        ts = self._period_last_ts

        if self._variant == "demark":
            raw_levels = _compute_demark(h, lo, c, o)
        else:
            compute_fn = _COMPUTE[self._variant]
            raw_levels = compute_fn(h, lo, c)  # type: ignore[operator]

        zone_half = 0.1 * self._atr.value if self._atr.ready else 0.0
        source = f"pivot_{self._variant}"

        levels: list[KeyLevel] = []
        for level_name, price in raw_levels:
            levels.append(KeyLevel(
                price=price,
                strength=_STRENGTH.get(level_name, 0.5),
                bounce_count=0,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=price + zone_half,
                zone_lower=price - zone_half,
                source=source,  # type: ignore[arg-type]
                meta=PivotPointMeta(
                    variant=self._variant,
                    level_name=level_name,
                    period_high=h,
                    period_low=lo,
                    period_close=c,
                ),
            ))
        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._bar_count = 0
        self._period_high = float("-inf")
        self._period_low = float("inf")
        self._period_open = 0.0
        self._period_close = 0.0
        self._period_last_ts = 0
        self._levels = []
