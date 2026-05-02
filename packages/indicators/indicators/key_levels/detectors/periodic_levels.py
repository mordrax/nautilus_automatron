"""PeriodicLevelDetector — PDH/PDL, PWH/PWL, PMH/PML (lifecycle-tracked).

Tracks running high/low for daily, weekly, and/or monthly periods. When a
period rolls over, the completed period's high & low are emitted as new
levels. Levels are born at the close of the prior period and live until they
are broken or aged out.

Daily levels typically last 1 trading day (default ~50 bars idle), weekly
~5 days, monthly ~22 days — `max_idle_bars` is per-period and overridable.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PeriodicLevelMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector

PeriodType = Literal["daily", "weekly", "monthly"]


_DEFAULT_IDLE_BARS: dict[PeriodType, int] = {
    "daily": 200,
    "weekly": 1000,
    "monthly": 4000,
}


@dataclass
class _PeriodAccumulator:
    high: float = float("-inf")
    low: float = float("inf")
    period_start: datetime.date | None = None
    has_data: bool = False


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    role: Literal["high", "low"]
    centroid: float
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    period: PeriodType
    period_start_iso: str
    max_idle_bars: int


def _period_key(dt: datetime.datetime, period: PeriodType) -> object:
    d = dt.date()
    if period == "daily":
        return d
    if period == "weekly":
        iso = d.isocalendar()
        return (iso[0], iso[1])
    return (d.year, d.month)


class PeriodicLevelDetector:

    def __init__(
        self,
        periods: tuple[PeriodType, ...] = ("daily",),
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: dict[PeriodType, int] | None = None,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._periods = periods
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = {**_DEFAULT_IDLE_BARS, **(max_idle_bars or {})}
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._accumulators: dict[PeriodType, _PeriodAccumulator] = {
            p: _PeriodAccumulator() for p in periods
        }
        self._prev_keys: dict[PeriodType, object | None] = {p: None for p in periods}

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "periodic_level"

    @property
    def warmup_bars(self) -> int:
        return 1

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
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

        if self._atr.ready:
            tolerance = 0.25 * self._atr.value
            for lvl in self._tracked:
                if lvl.end_ts is None:
                    self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)
            if swing is not None:
                for lvl in self._tracked:
                    if lvl.end_ts is not None or lvl.side != swing.side:
                        continue
                    if abs(swing.price - lvl.centroid) <= tolerance:
                        lvl.bounce_count += 1
                        lvl.last_touch_ts = swing.ts

        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        bar_date = dt.date()

        for period in self._periods:
            key = _period_key(dt, period)
            acc = self._accumulators[period]

            if self._prev_keys[period] is not None and key != self._prev_keys[period]:
                if acc.has_data:
                    self._emit_period_levels(period, acc, ts)
                acc.high = high
                acc.low = low
                acc.period_start = bar_date
                acc.has_data = True
            else:
                if not acc.has_data:
                    acc.high = high
                    acc.low = low
                    acc.period_start = bar_date
                    acc.has_data = True
                else:
                    acc.high = max(acc.high, high)
                    acc.low = min(acc.low, low)

            self._prev_keys[period] = key

    def _emit_period_levels(
        self, period: PeriodType, acc: _PeriodAccumulator, ts: int
    ) -> None:
        period_start = acc.period_start or datetime.date(2000, 1, 1)
        date_iso = period_start.isoformat()
        idle_bars = self._max_idle_bars[period]

        for role, price in (("high", acc.high), ("low", acc.low)):
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=role,  # type: ignore[arg-type]
                role=role,  # type: ignore[arg-type]
                centroid=price,
                start_ts=ts,
                end_ts=None,
                bounce_count=1,
                touch_count=0,
                last_touch_ts=ts,
                bars_through=0,
                period=period,
                period_start_iso=date_iso,
                max_idle_bars=idle_bars,
            ))
            self._next_id += 1

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
        idle_ns = lvl.max_idle_bars * bar_interval
        if ts - lvl.last_touch_ts > idle_ns:
            lvl.end_ts = lvl.last_touch_ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            decay = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            decay = max(0.0, min(1.0, decay))
            strength = max(0.0, min(1.0, 0.8 * decay))

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="periodic_level",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid,
                zone_lower=lvl.centroid,
                meta=PeriodicLevelMeta(
                    period=lvl.period,
                    role=lvl.role,
                    period_start_iso=lvl.period_start_iso,
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
        self._accumulators = {p: _PeriodAccumulator() for p in self._periods}
        self._prev_keys = {p: None for p in self._periods}
        self._tracked.clear()
        self._next_id = 0
