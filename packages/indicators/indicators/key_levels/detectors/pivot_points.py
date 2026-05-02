"""PivotPointDetector — period-anchored S/R levels (lifecycle-tracked).

Each completed period (e.g., a trading day) yields a fresh set of pivot levels
(P, R1/R2/R3..., S1/S2/S3...). The set is born when the period closes and
lives through the *next* period — at which point the next period's set is
emitted and the old set is finalized at the boundary timestamp.

Five formula variants supported: standard, fibonacci, camarilla, woodie,
demark. Each variant is exposed via a separate registry id (``pivot_standard``,
``pivot_fibonacci``, ...) so the frontend can toggle them independently.

`bounce_count` increments on swing-pivot touches; `touch_count` on bar-level
overlaps with the tolerance band around the centroid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PivotPointMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector

PivotVariant = Literal["standard", "fibonacci", "camarilla", "woodie", "demark"]

_LEVEL_BASE_STRENGTH: dict[str, float] = {
    "PP": 1.0,
    "R1": 0.8, "S1": 0.8,
    "R2": 0.6, "S2": 0.6,
    "R3": 0.4, "S3": 0.4,
    "R4": 0.3, "S4": 0.3,
}

_PIVOT_SOURCE: dict[PivotVariant, str] = {
    "standard": "pivot_standard",
    "fibonacci": "pivot_fibonacci",
    "camarilla": "pivot_camarilla",
    "woodie": "pivot_woodie",
    "demark": "pivot_demark",
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


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    centroid: float
    members: list[float]
    member_ts: list[int]
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    level_name: str
    period_high: float
    period_low: float
    period_close: float
    base_strength: float


class PivotPointDetector:

    def __init__(
        self,
        variant: PivotVariant = "standard",
        period_bars: int = 24,
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._variant: PivotVariant = variant
        self._source = _PIVOT_SOURCE[variant]
        self._period_bars = period_bars
        self._atr_period = atr_period
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        # Period accumulator state.
        self._bar_count: int = 0
        self._period_high: float = float("-inf")
        self._period_low: float = float("inf")
        self._period_open: float = 0.0
        self._period_close: float = 0.0
        self._period_last_ts: int = 0

        self._tracked: list[_TrackedLevel] = []
        # Indices of the currently-active period set (so we can finalize them
        # when a new period emits).
        self._active_period_ids: list[int] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return self._source

    @property
    def warmup_bars(self) -> int:
        return self._period_bars

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        open_ = float(bar.open)
        ts = bar.ts_event

        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        self._bar_index += 1

        # Per-bar lifecycle update on existing levels.
        if self._atr.ready:
            atr_value = self._atr.value
            tolerance = 0.25 * atr_value
            for idx in self._active_period_ids:
                lvl = self._tracked[idx]
                if lvl.end_ts is not None:
                    continue
                self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

            if swing is not None:
                self._attach_swing(swing.price, swing.ts, swing.side, tolerance)

        # Accumulate the period.
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

        # Period complete — emit a new set, finalize the previous set.
        if self._bar_count >= self._period_bars:
            self._emit_period_levels(ts)
            self._bar_count = 0
            self._period_high = float("-inf")
            self._period_low = float("inf")
            self._period_open = 0.0
            self._period_close = 0.0

    def _emit_period_levels(self, ts: int) -> None:
        h = self._period_high
        lo = self._period_low
        c = self._period_close
        o = self._period_open

        if self._variant == "demark":
            raw_levels = _compute_demark(h, lo, c, o)
        elif self._variant == "fibonacci":
            raw_levels = _compute_fibonacci(h, lo, c)
        elif self._variant == "camarilla":
            raw_levels = _compute_camarilla(h, lo, c)
        elif self._variant == "woodie":
            raw_levels = _compute_woodie(h, lo, c)
        else:
            raw_levels = _compute_standard(h, lo, c)

        # Finalize the previous period's set at the boundary.
        for idx in self._active_period_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is None:
                lvl.end_ts = ts

        new_active: list[int] = []
        # Use PP price as the side reference: levels priced above PP are
        # resistance (high), below PP are support (low).
        pp_price = next((p for name, p in raw_levels if name == "PP"), c)
        for level_name, price in raw_levels:
            side: Literal["high", "low"] = (
                "high" if price >= pp_price else "low"
            )
            base_strength = _LEVEL_BASE_STRENGTH.get(level_name, 0.5)
            idx = len(self._tracked)
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=side,
                centroid=price,
                members=[price],
                member_ts=[ts],
                start_ts=ts,
                end_ts=None,
                bounce_count=0,
                touch_count=0,
                last_touch_ts=ts,
                bars_through=0,
                level_name=level_name,
                period_high=h,
                period_low=lo,
                period_close=c,
                base_strength=base_strength,
            ))
            self._next_id += 1
            new_active.append(idx)

        self._active_period_ids = new_active

    def _apply_bar_to_level(
        self,
        lvl: _TrackedLevel,
        high: float,
        low: float,
        close: float,
        ts: int,
        tolerance: float,
    ) -> None:
        atr_value = self._atr.value
        if lvl.side == "high":
            beyond = close > lvl.centroid + self._break_atr_multiple * atr_value
        else:
            beyond = close < lvl.centroid - self._break_atr_multiple * atr_value

        if beyond:
            lvl.bars_through += 1
        else:
            lvl.bars_through = 0

        if lvl.bars_through >= self._break_consecutive_bars:
            lvl.end_ts = ts
            return

        band_upper = lvl.centroid + tolerance
        band_lower = lvl.centroid - tolerance
        if low <= band_upper and high >= band_lower:
            lvl.touch_count += 1
            lvl.last_touch_ts = ts

        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - lvl.last_touch_ts > idle_ns:
            lvl.end_ts = lvl.last_touch_ts

    def _attach_swing(
        self,
        price: float,
        ts: int,
        side: Literal["high", "low"],
        tolerance: float,
    ) -> None:
        for idx in self._active_period_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is not None or lvl.side != side:
                continue
            if abs(price - lvl.centroid) <= tolerance:
                lvl.bounce_count += 1
                lvl.last_touch_ts = ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            decay = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            decay = max(0.0, min(1.0, decay))
            strength = max(0.0, min(1.0, lvl.base_strength * decay))

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source=self._source,  # type: ignore[arg-type]
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid,
                zone_lower=lvl.centroid,
                meta=PivotPointMeta(
                    variant=self._variant,
                    level_name=lvl.level_name,
                    period_high=lvl.period_high,
                    period_low=lvl.period_low,
                    period_close=lvl.period_close,
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._swing_detector.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._bar_count = 0
        self._period_high = float("-inf")
        self._period_low = float("inf")
        self._period_open = 0.0
        self._period_close = 0.0
        self._period_last_ts = 0
        self._tracked.clear()
        self._active_period_ids.clear()
        self._next_id = 0
