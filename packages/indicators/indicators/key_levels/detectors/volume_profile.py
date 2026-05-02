"""VolumeProfileDetector — POC, VAH, VAL levels per non-overlapping period
(lifecycle-tracked).

Each period of `lookback_bars` produces a POC (Point of Control), Value Area
High and Value Area Low. A level is born when its period closes (the POC/VAH/
VAL is computed from the period's volume distribution) and ends when:

- the next period closes (the previous period's levels are finalized)
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

from indicators.key_levels.model import KeyLevel, VolumeProfileMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


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
    node_type: Literal["poc", "vah", "val"]
    volume_concentration: float
    bin_volume: float
    atr_at_emit: float


class VolumeProfileDetector:

    def __init__(
        self,
        lookback_bars: int = 50,
        bin_count: int = 50,
        value_area_pct: float = 0.7,
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._lookback_bars = lookback_bars
        self._bin_count = bin_count
        self._value_area_pct = value_area_pct
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

        # Buffer the current period's bars.
        self._period_bars: list[tuple[float, float, float, float, int]] = []

        self._tracked: list[_TrackedLevel] = []
        # Active period level ids — finalized when the next period closes.
        self._active_ids: list[int] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "volume_profile"

    @property
    def warmup_bars(self) -> int:
        return self._lookback_bars

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

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        self._bar_index += 1

        # Buffer the bar into the current period.
        self._period_bars.append((high, low, close, volume, ts))

        if not self._atr.ready:
            return

        atr_value = self._atr.value
        tolerance = 0.25 * atr_value

        # Per-bar lifecycle on active levels.
        for idx in self._active_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is None:
                self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # Attach swings to active same-side levels.
        if swing is not None:
            for idx in self._active_ids:
                lvl = self._tracked[idx]
                if lvl.end_ts is not None or lvl.side != swing.side:
                    continue
                if abs(swing.price - lvl.centroid) <= tolerance:
                    lvl.bounce_count += 1
                    lvl.last_touch_ts = swing.ts

        # When the period fills, emit a fresh set and reset the buffer.
        if len(self._period_bars) >= self._lookback_bars:
            self._close_period(close, ts, atr_value)

    def _close_period(self, close: float, ts: int, atr_value: float) -> None:
        # Finalize any still-active levels from the previous period.
        for idx in self._active_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is None:
                lvl.end_ts = ts

        new_active = self._compute_period_levels(close, ts, atr_value)
        self._active_ids = new_active
        self._period_bars = []

    def _compute_period_levels(
        self, close: float, ts: int, atr_value: float,
    ) -> list[int]:
        bars = self._period_bars
        if len(bars) < 2:
            return []

        highs = [b[0] for b in bars]
        lows = [b[1] for b in bars]
        price_min = min(lows)
        price_max = max(highs)
        price_range = price_max - price_min

        if price_range <= 0:
            return []

        bin_size = price_range / self._bin_count
        volume_bins = [0.0] * self._bin_count

        for high, low, _close, volume, _ts in bars:
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
            return []

        # POC: max volume bin.
        poc_idx = max(range(self._bin_count), key=lambda i: volume_bins[i])
        poc_price = price_min + (poc_idx + 0.5) * bin_size
        poc_volume = volume_bins[poc_idx]

        # Value area: expand from POC.
        va_volume = poc_volume
        va_low_idx = poc_idx
        va_high_idx = poc_idx
        target_volume = total_volume * self._value_area_pct

        while va_volume < target_volume and (
            va_low_idx > 0 or va_high_idx < self._bin_count - 1
        ):
            expand_low = (
                volume_bins[va_low_idx - 1] if va_low_idx > 0 else -1.0
            )
            expand_high = (
                volume_bins[va_high_idx + 1]
                if va_high_idx < self._bin_count - 1
                else -1.0
            )
            if expand_high >= expand_low:
                va_high_idx += 1
                va_volume += volume_bins[va_high_idx]
            else:
                va_low_idx -= 1
                va_volume += volume_bins[va_low_idx]

        va_high_price = price_min + (va_high_idx + 1) * bin_size
        va_low_price = price_min + va_low_idx * bin_size

        period_start_ts = bars[0][4]

        new_active: list[int] = []
        for node_type, price, bin_vol in (
            ("poc", poc_price, poc_volume),
            ("vah", va_high_price, volume_bins[va_high_idx]),
            ("val", va_low_price, volume_bins[va_low_idx]),
        ):
            side: Literal["high", "low"] = (
                "high" if price >= close else "low"
            )
            concentration = bin_vol / total_volume if total_volume else 0.0

            idx = len(self._tracked)
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=side,
                centroid=price,
                start_ts=period_start_ts,
                end_ts=None,
                bounce_count=0,
                touch_count=0,
                last_touch_ts=ts,
                bars_through=0,
                node_type=node_type,  # type: ignore[arg-type]
                volume_concentration=concentration,
                bin_volume=bin_vol,
                atr_at_emit=atr_value,
            ))
            self._next_id += 1
            new_active.append(idx)

        return new_active

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
            base = 1.0 if lvl.node_type == "poc" else 0.7
            strength = max(0.0, min(1.0, base * decay))

            zone_half = 0.25 * lvl.atr_at_emit

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="volume_profile",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid + zone_half,
                zone_lower=lvl.centroid - zone_half,
                meta=VolumeProfileMeta(
                    volume_concentration=lvl.volume_concentration,
                    node_type=(
                        "poc" if lvl.node_type == "poc"
                        else "va_high" if lvl.node_type == "vah"
                        else "va_low"
                    ),
                    bin_volume=lvl.bin_volume,
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
        self._period_bars = []
        self._tracked.clear()
        self._active_ids.clear()
        self._next_id = 0
