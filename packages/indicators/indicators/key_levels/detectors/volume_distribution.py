"""VolumeDistributionDetector — context-aware volume POC levels (lifecycle-tracked).

Identifies structural contexts between consecutive confirmed swings and emits
one POC-of-context level per qualifying context. A level is born when its
context closes (the second of the two swings is confirmed and the context has
enough bars). It lives until:

- a sustained close beyond the level for `break_consecutive_bars` bars (break)
- aged-out (no touch for `max_idle_bars` bars)

`bounce_count` increments on swing-pivot touches; `touch_count` on bar-level
overlaps with the tolerance band around the centroid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, VolumeDistributionMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import Swing, SwingDetector


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    centroid: float
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    context: Literal["consolidation", "peak", "trough", "range"]
    volume_concentration: float
    context_bar_count: int
    atr_at_emit: float


def _classify_context(
    prev_swing: Swing, curr_swing: Swing,
) -> Literal["consolidation", "peak", "trough", "range"]:
    if prev_swing.side == "high" and curr_swing.side == "low":
        return "trough"
    if prev_swing.side == "low" and curr_swing.side == "high":
        return "peak"
    if prev_swing.side == curr_swing.side:
        return "consolidation"
    return "range"


class VolumeDistributionDetector:

    def __init__(
        self,
        swing_period: int = 5,
        min_context_bars: int = 10,
        bin_count: int = 30,
        atr_period: int = 14,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._swing_period = swing_period
        self._min_context_bars = min_context_bars
        self._bin_count = bin_count
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
        # Buffer all bars since detector start (lookups by bar_index).
        self._bars: list[tuple[float, float, float, float, int]] = []
        self._swings: list[Swing] = []
        # Identifies (prev.ts, curr.ts) pairs that already produced a level.
        self._processed_pairs: set[tuple[int, int]] = set()

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "volume_distribution"

    @property
    def warmup_bars(self) -> int:
        return self._swing_detector.warmup_bars + self._min_context_bars

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)
        self._bars.append((high, low, close, volume, ts))

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        if swing is not None:
            self._swings.append(swing)

        self._bar_index += 1

        if not self._atr.ready:
            return

        atr_value = self._atr.value
        tolerance = 0.25 * atr_value

        # Per-bar lifecycle on active levels.
        for lvl in self._tracked:
            if lvl.end_ts is None:
                self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # Attach swing to closest active same-side level.
        if swing is not None:
            best: _TrackedLevel | None = None
            best_dist = tolerance
            for lvl in self._tracked:
                if lvl.end_ts is not None or lvl.side != swing.side:
                    continue
                dist = abs(swing.price - lvl.centroid)
                if dist <= best_dist:
                    best = lvl
                    best_dist = dist
            if best is not None:
                best.bounce_count += 1
                best.last_touch_ts = swing.ts

        # Try to emit fresh levels for any newly-formable swing pairs.
        if len(self._swings) >= 2:
            self._maybe_emit(ts, atr_value)

    def _maybe_emit(self, ts: int, atr_value: float) -> None:
        for i in range(1, len(self._swings)):
            prev = self._swings[i - 1]
            curr = self._swings[i]
            key = (prev.ts, curr.ts)
            if key in self._processed_pairs:
                continue

            start_idx = max(0, prev.bar_index)
            end_idx = min(len(self._bars) - 1, curr.bar_index)
            if end_idx <= start_idx:
                self._processed_pairs.add(key)
                continue

            context_bars = self._bars[start_idx : end_idx + 1]
            if len(context_bars) < self._min_context_bars:
                self._processed_pairs.add(key)
                continue

            self._processed_pairs.add(key)
            level = self._volume_poc(context_bars, prev, curr, atr_value)
            if level is not None:
                self._tracked.append(level)

    def _volume_poc(
        self,
        context_bars: list[tuple[float, float, float, float, int]],
        prev: Swing,
        curr: Swing,
        atr_value: float,
    ) -> _TrackedLevel | None:
        highs = [b[0] for b in context_bars]
        lows = [b[1] for b in context_bars]
        price_min = min(lows)
        price_max = max(highs)
        price_range = price_max - price_min
        if price_range <= 0:
            return None

        bin_size = price_range / self._bin_count
        volume_bins = [0.0] * self._bin_count

        for high, low, _close, volume, _ts in context_bars:
            if volume <= 0 or high <= low:
                continue
            bar_range = high - low
            for bi in range(self._bin_count):
                bin_low = price_min + bi * bin_size
                bin_high = bin_low + bin_size
                overlap_low = max(low, bin_low)
                overlap_high = min(high, bin_high)
                if overlap_high > overlap_low:
                    proportion = (overlap_high - overlap_low) / bar_range
                    volume_bins[bi] += volume * proportion

        total_volume = sum(volume_bins)
        if total_volume <= 0:
            return None

        poc_idx = max(range(self._bin_count), key=lambda i: volume_bins[i])
        poc_price = price_min + (poc_idx + 0.5) * bin_size
        poc_volume = volume_bins[poc_idx]
        concentration = poc_volume / total_volume
        context = _classify_context(prev, curr)

        # Side determined by relation to the most recent swing close.
        last_close = context_bars[-1][2]
        side: Literal["high", "low"] = "high" if poc_price >= last_close else "low"

        idx = self._next_id
        self._next_id += 1
        return _TrackedLevel(
            id=idx,
            side=side,
            centroid=poc_price,
            start_ts=curr.ts,
            end_ts=None,
            bounce_count=0,
            touch_count=0,
            last_touch_ts=curr.ts,
            bars_through=0,
            context=context,
            volume_concentration=concentration,
            context_bar_count=len(context_bars),
            atr_at_emit=atr_value,
        )

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
            # Stronger when the POC dominates the histogram.
            base = min(1.0, lvl.volume_concentration * self._bin_count)
            strength = max(0.0, min(1.0, base * decay))

            zone_half = 0.25 * lvl.atr_at_emit

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="volume_distribution",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid + zone_half,
                zone_lower=lvl.centroid - zone_half,
                meta=VolumeDistributionMeta(
                    context=lvl.context,
                    volume_concentration=lvl.volume_concentration,
                    context_bar_count=lvl.context_bar_count,
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
        self._bars.clear()
        self._swings.clear()
        self._processed_pairs.clear()
        self._tracked.clear()
        self._next_id = 0
