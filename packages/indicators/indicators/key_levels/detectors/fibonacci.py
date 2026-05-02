"""Fibonacci level detectors — retracement and extension (lifecycle-tracked).

Both detectors anchor a fan of levels at standard Fibonacci ratios from a
swing leg. When a new leg supersedes the current anchor, the previous fan is
finalized at that timestamp and a fresh fan is emitted.

- Retracement: support/resistance levels *between* the anchoring swing
  high/low pair, at ratios 0.236 / 0.382 / 0.5 / 0.618 / 0.786.
- Extension: projected levels *beyond* point C in an A-B-C swing pattern at
  ratios 1.0 / 1.272 / 1.618 / 2.0 / 2.618.

`bounce_count` increments on swing-pivot touches; `touch_count` on bar-level
overlaps with the tolerance band around the centroid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import FibonacciMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import Swing, SwingDetector

RETRACEMENT_RATIOS: tuple[float, ...] = (0.236, 0.382, 0.5, 0.618, 0.786)
EXTENSION_RATIOS: tuple[float, ...] = (1.0, 1.272, 1.618, 2.0, 2.618)

_RATIO_BASE_STRENGTH: dict[float, float] = {
    0.618: 1.0,
    0.5: 0.8,
    0.382: 0.6,
    0.786: 0.5,
    0.236: 0.4,
}

_EXT_RATIO_BASE_STRENGTH: dict[float, float] = {
    1.618: 1.0,
    1.0: 0.8,
    1.272: 0.7,
    2.0: 0.6,
    2.618: 0.5,
}


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
    ratio: float
    swing_high: float
    swing_low: float
    direction: Literal["retracement", "extension"]
    base_strength: float
    atr_at_emit: float


def _apply_bar(
    lvl: _TrackedLevel,
    high: float,
    low: float,
    close: float,
    ts: int,
    atr_value: float,
    tolerance: float,
    break_atr_multiple: float,
    break_consecutive_bars: int,
    bar_interval_ns: int,
    max_idle_bars: int,
) -> None:
    if lvl.side == "high":
        beyond = close > lvl.centroid + break_atr_multiple * atr_value
    else:
        beyond = close < lvl.centroid - break_atr_multiple * atr_value

    if beyond:
        lvl.bars_through += 1
    else:
        lvl.bars_through = 0

    if lvl.bars_through >= break_consecutive_bars:
        lvl.end_ts = ts
        return

    band_upper = lvl.centroid + tolerance
    band_lower = lvl.centroid - tolerance
    if low <= band_upper and high >= band_lower:
        lvl.touch_count += 1
        lvl.last_touch_ts = ts

    idle_ns = max_idle_bars * bar_interval_ns
    if ts - lvl.last_touch_ts > idle_ns:
        lvl.end_ts = lvl.last_touch_ts


class FibonacciRetracementDetector:

    def __init__(
        self,
        swing_period: int = 5,
        min_swing_atr_multiple: float = 2.0,
        atr_period: int = 14,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._swing_period = swing_period
        self._min_swing_atr_multiple = min_swing_atr_multiple
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._swing_detector = SwingDetector(period=swing_period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._last_swing_high: Swing | None = None
        self._last_swing_low: Swing | None = None

        self._tracked: list[_TrackedLevel] = []
        self._active_set_ids: list[int] = []
        # The (sh.ts, sl.ts) tuple identifying the leg that produced the
        # current active fan — used to detect "same leg, no re-emit".
        self._active_leg_key: tuple[int, int] | None = None
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "fib_retracement"

    @property
    def warmup_bars(self) -> int:
        return self._swing_period * 2 + 1

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

        # Per-bar lifecycle on the active fan.
        if self._atr.ready:
            atr_value = self._atr.value
            tolerance = 0.25 * atr_value
            bar_interval = self._bar_interval_ns or 1
            for idx in self._active_set_ids:
                lvl = self._tracked[idx]
                if lvl.end_ts is None:
                    _apply_bar(
                        lvl, high, low, close, ts, atr_value, tolerance,
                        self._break_atr_multiple,
                        self._break_consecutive_bars,
                        bar_interval,
                        self._max_idle_bars,
                    )

            if swing is not None:
                _attach_swing_to_set(
                    self._tracked,
                    self._active_set_ids,
                    swing.price,
                    swing.ts,
                    swing.side,
                    tolerance,
                )

        # Update last-known swings.
        if swing is not None:
            if swing.side == "high":
                self._last_swing_high = swing
            else:
                self._last_swing_low = swing

        # Emit a fresh fan when both swings exist and the leg is new.
        if (
            self._atr.ready
            and self._last_swing_high is not None
            and self._last_swing_low is not None
        ):
            self._maybe_emit_fan(ts)

    def _maybe_emit_fan(self, ts: int) -> None:
        sh = self._last_swing_high
        sl = self._last_swing_low
        assert sh is not None and sl is not None  # noqa: S101

        leg_key = (sh.ts, sl.ts)
        if leg_key == self._active_leg_key:
            return

        atr = self._atr.value
        swing_range = abs(sh.price - sl.price)
        if swing_range < self._min_swing_atr_multiple * atr:
            return

        # Finalize the previous fan at this boundary.
        for idx in self._active_set_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is None:
                lvl.end_ts = ts

        uptrend = sl.bar_index < sh.bar_index
        most_recent_ts = max(sh.ts, sl.ts)

        new_active: list[int] = []
        for ratio in RETRACEMENT_RATIOS:
            if uptrend:
                # Levels are support below the swing high.
                level_price = sh.price - ratio * swing_range
                side: Literal["high", "low"] = "low"
            else:
                # Levels are resistance above the swing low.
                level_price = sl.price + ratio * swing_range
                side = "high"

            base_strength = _RATIO_BASE_STRENGTH.get(ratio, 0.4)
            idx = len(self._tracked)
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=side,
                centroid=level_price,
                members=[level_price],
                member_ts=[most_recent_ts],
                start_ts=most_recent_ts,
                end_ts=None,
                bounce_count=0,
                touch_count=0,
                last_touch_ts=most_recent_ts,
                bars_through=0,
                ratio=ratio,
                swing_high=sh.price,
                swing_low=sl.price,
                direction="retracement",
                base_strength=base_strength,
                atr_at_emit=atr,
            ))
            self._next_id += 1
            new_active.append(idx)

        self._active_set_ids = new_active
        self._active_leg_key = leg_key

    def levels(self) -> list[KeyLevel]:
        return _make_levels(
            self._tracked,
            self._strength_decay_k,
            self._min_touches,
            source="fib_retracement",
        )

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._last_swing_high = None
        self._last_swing_low = None
        self._tracked.clear()
        self._active_set_ids.clear()
        self._active_leg_key = None
        self._next_id = 0


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------


class FibonacciExtensionDetector:

    def __init__(
        self,
        swing_period: int = 5,
        min_swing_atr_multiple: float = 2.0,
        atr_period: int = 14,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._swing_period = swing_period
        self._min_swing_atr_multiple = min_swing_atr_multiple
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._swing_detector = SwingDetector(period=swing_period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None
        self._swings: list[Swing] = []

        self._tracked: list[_TrackedLevel] = []
        self._active_set_ids: list[int] = []
        # Identifies the (a.ts, b.ts, c.ts) triplet whose fan is currently
        # active.
        self._active_abc_key: tuple[int, int, int] | None = None
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "fib_extension"

    @property
    def warmup_bars(self) -> int:
        return self._swing_period * 2 + 1

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
            atr_value = self._atr.value
            tolerance = 0.25 * atr_value
            bar_interval = self._bar_interval_ns or 1
            for idx in self._active_set_ids:
                lvl = self._tracked[idx]
                if lvl.end_ts is None:
                    _apply_bar(
                        lvl, high, low, close, ts, atr_value, tolerance,
                        self._break_atr_multiple,
                        self._break_consecutive_bars,
                        bar_interval,
                        self._max_idle_bars,
                    )

            if swing is not None:
                _attach_swing_to_set(
                    self._tracked,
                    self._active_set_ids,
                    swing.price,
                    swing.ts,
                    swing.side,
                    tolerance,
                )

        if swing is not None:
            self._swings.append(swing)

        if self._atr.ready and len(self._swings) >= 3:
            self._maybe_emit_fan(ts)

    def _maybe_emit_fan(self, ts: int) -> None:
        a, b, c = self._swings[-3], self._swings[-2], self._swings[-1]

        abc_key = (a.ts, b.ts, c.ts)
        if abc_key == self._active_abc_key:
            return

        # Validate A-B-C alternation (must be low-high-low or high-low-high).
        if a.side == "low" and b.side == "high" and c.side == "low":
            uptrend = True
        elif a.side == "high" and b.side == "low" and c.side == "high":
            uptrend = False
        else:
            return

        atr = self._atr.value
        swing_range = abs(b.price - a.price)
        if swing_range < self._min_swing_atr_multiple * atr:
            return

        # Finalize the previous fan.
        for idx in self._active_set_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is None:
                lvl.end_ts = ts

        most_recent_ts = max(a.ts, b.ts, c.ts)
        swing_high = max(a.price, b.price, c.price)
        swing_low = min(a.price, b.price, c.price)

        new_active: list[int] = []
        for ratio in EXTENSION_RATIOS:
            if uptrend:
                ext_price = c.price + ratio * (b.price - a.price)
                side: Literal["high", "low"] = "high"
            else:
                ext_price = c.price - ratio * (a.price - b.price)
                side = "low"

            base_strength = _EXT_RATIO_BASE_STRENGTH.get(ratio, 0.4)
            idx = len(self._tracked)
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=side,
                centroid=ext_price,
                members=[ext_price],
                member_ts=[most_recent_ts],
                start_ts=most_recent_ts,
                end_ts=None,
                bounce_count=0,
                touch_count=0,
                last_touch_ts=most_recent_ts,
                bars_through=0,
                ratio=ratio,
                swing_high=swing_high,
                swing_low=swing_low,
                direction="extension",
                base_strength=base_strength,
                atr_at_emit=atr,
            ))
            self._next_id += 1
            new_active.append(idx)

        self._active_set_ids = new_active
        self._active_abc_key = abc_key

    def levels(self) -> list[KeyLevel]:
        return _make_levels(
            self._tracked,
            self._strength_decay_k,
            self._min_touches,
            source="fib_extension",
        )

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._swings.clear()
        self._tracked.clear()
        self._active_set_ids.clear()
        self._active_abc_key = None
        self._next_id = 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _attach_swing_to_set(
    tracked: list[_TrackedLevel],
    active_ids: list[int],
    price: float,
    ts: int,
    side: Literal["high", "low"],
    tolerance: float,
) -> None:
    for idx in active_ids:
        lvl = tracked[idx]
        if lvl.end_ts is not None or lvl.side != side:
            continue
        if abs(price - lvl.centroid) <= tolerance:
            lvl.bounce_count += 1
            lvl.last_touch_ts = ts


def _make_levels(
    tracked: list[_TrackedLevel],
    strength_decay_k: float,
    min_touches: int,
    source: Literal["fib_retracement", "fib_extension"],
) -> list[KeyLevel]:
    out: list[KeyLevel] = []
    for lvl in tracked:
        decay = math.exp(
            -(lvl.bounce_count - min_touches) / strength_decay_k
        )
        decay = max(0.0, min(1.0, decay))
        strength = max(0.0, min(1.0, lvl.base_strength * decay))

        zone_half = 0.15 * lvl.atr_at_emit

        out.append(KeyLevel(
            price=lvl.centroid,
            strength=strength,
            start_ts=lvl.start_ts,
            end_ts=lvl.end_ts,
            source=source,
            bounce_count=lvl.bounce_count,
            zone_upper=lvl.centroid + zone_half,
            zone_lower=lvl.centroid - zone_half,
            meta=FibonacciMeta(
                ratio=lvl.ratio,
                swing_high=lvl.swing_high,
                swing_low=lvl.swing_low,
                direction=lvl.direction,
                side=lvl.side,
                touch_count=lvl.touch_count,
            ),
        ))
    return out
