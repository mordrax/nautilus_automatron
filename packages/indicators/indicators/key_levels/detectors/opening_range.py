"""OpeningRangeDetector — first N minutes of a session high/low
(lifecycle-tracked).

Tracks the high and low of the first ``range_minutes`` minutes after the
configured market open. Once the opening-range window closes, the high & low
are emitted as levels (ORH / ORL). They live until they break, age out, or
the session ends (next day rollover).

A new day automatically resets the tracker — open levels from the previous
day are finalized at the day boundary.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, OpeningRangeMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


@dataclass
class _RangeAccumulator:
    high: float = float("-inf")
    low: float = float("inf")
    range_start_ts: int = 0
    locked: bool = False
    current_date: datetime.date | None = None
    has_data: bool = False
    emitted_ids: tuple[int, int] | None = None


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


class OpeningRangeDetector:

    def __init__(
        self,
        range_minutes: int = 30,
        market_open_hour_utc: int = 9,
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._range_minutes = range_minutes
        self._market_open_hour_utc = market_open_hour_utc
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

        self._acc = _RangeAccumulator()
        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "opening_range"

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

        # Detect new day — finalize emitted levels and reset accumulator.
        if self._acc.current_date is not None and bar_date != self._acc.current_date:
            if self._acc.emitted_ids is not None:
                for emitted_id in self._acc.emitted_ids:
                    for lvl in self._tracked:
                        if lvl.id == emitted_id and lvl.end_ts is None:
                            lvl.end_ts = ts
            self._acc = _RangeAccumulator()

        open_start = datetime.datetime(
            bar_date.year, bar_date.month, bar_date.day,
            self._market_open_hour_utc, 0, 0,
            tzinfo=datetime.timezone.utc,
        )
        open_end = open_start + datetime.timedelta(minutes=self._range_minutes)

        self._acc.current_date = bar_date

        if self._acc.locked:
            return

        if open_start <= dt < open_end:
            if not self._acc.has_data:
                self._acc.high = high
                self._acc.low = low
                self._acc.range_start_ts = ts
                self._acc.has_data = True
            else:
                self._acc.high = max(self._acc.high, high)
                self._acc.low = min(self._acc.low, low)
        elif dt >= open_end and self._acc.has_data and not self._acc.locked:
            self._acc.locked = True
            self._emit_levels(ts)

    def _emit_levels(self, ts: int) -> None:
        ids: list[int] = []
        for role, price in (("high", self._acc.high), ("low", self._acc.low)):
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
            ))
            ids.append(self._next_id)
            self._next_id += 1
        self._acc.emitted_ids = (ids[0], ids[1])

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
                source="opening_range",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid,
                zone_lower=lvl.centroid,
                meta=OpeningRangeMeta(
                    range_minutes=self._range_minutes,
                    role=lvl.role,
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
        self._acc = _RangeAccumulator()
        self._tracked.clear()
        self._next_id = 0
