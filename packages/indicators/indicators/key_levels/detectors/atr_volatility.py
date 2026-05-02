"""AtrVolatilityDetector — volatility bands at ATR multiples (lifecycle-tracked).

Anchors a fan of resistance / support bands at ``close +/- mult * ATR`` for
each multiplier. Each band is born when the indicator warms up, lives while
its centroid stays close to the natural anchor, and ends either by:

- a sustained close beyond the band for `break_consecutive_bars` bars (break)
- the natural anchor drifting far enough that a fresh band would replace this
  one (``band_replacement_atr * ATR`` rule — re-emits as a new tracked level)
- aged-out (no touch for ``max_idle_bars`` bars)

`bounce_count` increments on swing-pivot touches; `touch_count` on bar-level
overlaps with the tolerance band around the centroid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import AtrVolatilityMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


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
    multiplier: float
    anchor_price: float
    atr_at_emit: float


class AtrVolatilityDetector:

    def __init__(
        self,
        atr_period: int = 14,
        multipliers: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0),
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
        # When the natural band (close +/- mult * ATR) drifts beyond
        # ``band_replacement_atr * ATR`` from the existing centroid, finalize
        # the old level and emit a new one in its place.
        band_replacement_atr: float = 1.0,
    ) -> None:
        self._atr_period = atr_period
        self._multipliers = multipliers
        self._max_multiplier = max(multipliers) if multipliers else 1.0
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches
        self._band_replacement_atr = band_replacement_atr

        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0
        # Most-recent active band per (multiplier, side) for replacement
        # checks. None means we don't have one yet.
        self._active_band: dict[tuple[float, Literal["high", "low"]], int] = {}

    @property
    def name(self) -> str:
        return "atr_volatility"

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

        # 1) Per-bar lifecycle: break / touch / aged-out on existing levels.
        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # 2) Attach swing to any active band on the matching side.
        if swing is not None:
            self._attach_swing(swing.price, swing.ts, swing.side, tolerance)

        # 3) Emit / replace bands per multiplier.
        for mult in self._multipliers:
            for side in ("high", "low"):
                self._emit_or_replace_band(
                    side=side,  # type: ignore[arg-type]
                    mult=mult,
                    close=close,
                    atr_value=atr_value,
                    ts=ts,
                )

    def _emit_or_replace_band(
        self,
        side: Literal["high", "low"],
        mult: float,
        close: float,
        atr_value: float,
        ts: int,
    ) -> None:
        if side == "high":
            target = close + mult * atr_value
        else:
            target = close - mult * atr_value

        key = (mult, side)
        existing_id = self._active_band.get(key)
        if existing_id is not None:
            existing = self._tracked[existing_id]
            if existing.end_ts is None:
                drift = abs(existing.centroid - target)
                if drift <= self._band_replacement_atr * atr_value:
                    return
                # Drift exceeds replacement threshold — finalize and replace.
                existing.end_ts = ts

        # Emit a fresh tracked band.
        new_idx = len(self._tracked)
        self._tracked.append(_TrackedLevel(
            id=self._next_id,
            side=side,
            centroid=target,
            members=[target],
            member_ts=[ts],
            start_ts=ts,
            end_ts=None,
            bounce_count=0,
            touch_count=0,
            last_touch_ts=ts,
            bars_through=0,
            multiplier=mult,
            anchor_price=close,
            atr_at_emit=atr_value,
        ))
        self._next_id += 1
        self._active_band[key] = new_idx

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
            decay = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            decay = max(0.0, min(1.0, decay))
            # Higher-multiplier bands are inherently stronger reference points
            # (they represent rarer moves).
            base_strength = (
                lvl.multiplier / self._max_multiplier
                if self._max_multiplier else 1.0
            )
            strength = max(0.0, min(1.0, base_strength * decay))

            zone_half = 0.25 * lvl.atr_at_emit

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="atr_volatility",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid + zone_half,
                zone_lower=lvl.centroid - zone_half,
                meta=AtrVolatilityMeta(
                    atr_value=lvl.atr_at_emit,
                    multiplier=lvl.multiplier,
                    anchor_price=lvl.anchor_price,
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
        self._next_id = 0
        self._active_band.clear()
