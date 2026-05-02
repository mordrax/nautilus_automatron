"""PsychologicalLevelDetector — round-number key levels (lifecycle-tracked).

Round numbers (e.g. 1.1000, 1.1050, 1.1100 for FX; 100, 50, 25 for XAUUSD) act
as long-lived horizontals. Unlike cluster-based detectors, these levels are
*static* — they don't move with price. They are emitted once when discovered
near the current price and live until either:

- a sustained close beyond the level for `break_consecutive_bars` bars (break)
- the level falls outside the relevant range and never gets touched (very long
  ``max_idle_bars`` default — these levels are inherently long-lived).

`bounce_count` increments on swing-pivot touches; `touch_count` increments on
any bar whose range overlaps the tolerance band around the centroid. Strength
decays exponentially as touches accumulate (a level that has been tested many
times is weaker than a fresh one).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PsychologicalMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector

_TIER: tuple[Literal["major", "minor", "micro"], ...] = ("major", "minor", "micro")
_TIER_BASE_STRENGTH: dict[str, float] = {
    "major": 1.0,
    "minor": 0.7,
    "micro": 0.4,
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
    tier: Literal["major", "minor", "micro"]
    round_value: float
    base_strength: float


class PsychologicalLevelDetector:

    def __init__(
        self,
        tier_steps: dict[str, float],
        range_levels: int = 5,
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        # Psychological levels are inherently long-lived; default to a very
        # large idle threshold so they effectively only end on break.
        max_idle_bars: int = 100_000,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
        # `lookback` is accepted for API back-compat but not used in this
        # lifecycle implementation.
        lookback: int = 200,
    ) -> None:
        self._tier_steps = tier_steps
        self._range_levels = range_levels
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

        self._tracked: list[_TrackedLevel] = []
        # Track which (tier, round_value) pairs already have an active or
        # finalized tracked level so we don't re-emit duplicates.
        self._known_levels: set[tuple[str, float]] = set()
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "psychological"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period

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

        if not self._atr.ready:
            return

        atr_value = self._atr.value
        tolerance = 0.25 * atr_value

        # Per-bar lifecycle update (break / touch / aged-out).
        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # Attach a freshly confirmed swing to any nearby active level.
        if swing is not None:
            self._attach_swing(swing.price, swing.ts, swing.side, tolerance)

        # Emit any newly-relevant round-number levels around the current price.
        self._emit_levels_around(close, ts, atr_value)

    def _emit_levels_around(self, price: float, ts: int, atr_value: float) -> None:
        """Emit round-number levels within ``range_levels`` steps of the
        current price for each tier. Skips any (tier, round_value) we've
        already emitted.
        """
        for tier_name in _TIER:
            step = self._tier_steps.get(tier_name)
            if step is None or step <= 0:
                continue
            base = math.floor(price / step) * step
            base_strength = _TIER_BASE_STRENGTH.get(tier_name, 0.4)

            for i in range(-self._range_levels, self._range_levels + 1):
                level_price = base + i * step
                key = (tier_name, level_price)
                if key in self._known_levels:
                    continue

                # Side is determined by which side of the current price the
                # level sits on at emission time.
                side: Literal["high", "low"] = (
                    "high" if level_price >= price else "low"
                )

                self._tracked.append(_TrackedLevel(
                    id=self._next_id,
                    side=side,
                    centroid=level_price,
                    members=[level_price],
                    member_ts=[ts],
                    start_ts=ts,
                    end_ts=None,
                    bounce_count=0,
                    touch_count=0,
                    last_touch_ts=ts,
                    bars_through=0,
                    tier=tier_name,
                    round_value=level_price,
                    base_strength=base_strength,
                ))
                self._next_id += 1
                self._known_levels.add(key)

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

        # Break check: a sustained close beyond the level. Side determines
        # which direction is "beyond". The breaking bar does not count as a
        # touch.
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

        # Bar-level touch.
        band_upper = lvl.centroid + tolerance
        band_lower = lvl.centroid - tolerance
        if low <= band_upper and high >= band_lower:
            lvl.touch_count += 1
            lvl.last_touch_ts = ts

        # Aged-out check (rarely relevant given the large default).
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
        """If a confirmed swing falls within tolerance of any active level on
        the matching side, count it as a bounce.
        """
        for lvl in self._tracked:
            if lvl.end_ts is not None or lvl.side != side:
                continue
            if abs(price - lvl.centroid) <= tolerance:
                lvl.bounce_count += 1
                lvl.last_touch_ts = ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            # Strength decays as bounces accumulate; but it's also scaled by
            # the tier's base strength (major levels are always stronger than
            # micro levels at the same touch count).
            decay = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            decay = max(0.0, min(1.0, decay))
            strength = lvl.base_strength * decay
            strength = max(0.0, min(1.0, strength))

            zone_upper = lvl.centroid
            zone_lower = lvl.centroid

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="psychological",
                bounce_count=lvl.bounce_count,
                zone_upper=zone_upper,
                zone_lower=zone_lower,
                meta=PsychologicalMeta(
                    tier=lvl.tier,
                    round_value=lvl.round_value,
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
        self._tracked.clear()
        self._known_levels.clear()
        self._next_id = 0
