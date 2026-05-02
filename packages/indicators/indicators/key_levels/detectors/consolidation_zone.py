"""ConsolidationZoneDetector — horizontal price ranges (lifecycle-tracked).

Detects consolidation by checking the linear-regression slope of a rolling
window of highs/lows is near-zero AND the short-term ATR is compressed
relative to a longer-term ATR. When a zone is confirmed, the detector emits
a single zoned level (``zone_upper`` = range high, ``zone_lower`` = range
low, ``price`` = midpoint). The level lives until a sustained close beyond
the zone by ``break_atr_multiple * ATR`` (breakout) or ages out.

To avoid emitting a fresh zone every bar while the regime is stable, we
keep at most one *active* zone — once it ends, a new zone may form on
subsequent bars.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import ConsolidationZoneMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr


def _linear_slope(values: list[float]) -> float:
    """Mean-normalized linear-regression slope (scale-independent)."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_y = sum(values) / n
    if mean_y == 0:
        return 0.0
    mean_x = (n - 1) / 2.0
    num = 0.0
    den = 0.0
    for i, y in enumerate(values):
        dx = i - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    if den == 0:
        return 0.0
    return (num / den) / mean_y


@dataclass
class _TrackedZone:
    id: int
    centroid: float
    range_high: float
    range_low: float
    slope: float
    bar_count: int
    duration_bars: int
    range_atr_multiple: float
    start_ts: int
    end_ts: int | None
    last_touch_ts: int
    touch_count: int
    side: Literal["high", "low"]


class ConsolidationZoneDetector:

    def __init__(
        self,
        min_range_bars: int = 20,
        max_slope: float = 0.001,
        volatility_threshold: float = 0.5,
        atr_period: int = 14,
        break_atr_multiple: float = 1.0,
        max_idle_bars: int = 200,
    ) -> None:
        self._min_range_bars = min_range_bars
        self._max_slope = max_slope
        self._volatility_threshold = volatility_threshold
        self._atr_period = atr_period
        self._break_atr_multiple = break_atr_multiple
        self._max_idle_bars = max_idle_bars

        self._atr = StreamingAtr(period=atr_period)
        self._long_atr = StreamingAtr(period=atr_period * 3)

        self._highs: deque[float] = deque(maxlen=min_range_bars)
        self._lows: deque[float] = deque(maxlen=min_range_bars)

        self._tracked: list[_TrackedZone] = []
        self._active_id: int | None = None
        self._next_id: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

    @property
    def name(self) -> str:
        return "consolidation_zone"

    @property
    def warmup_bars(self) -> int:
        return max(self._min_range_bars, self._atr_period * 3)

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
        self._long_atr.update(high, low, close)

        # Per-bar lifecycle on the active zone.
        if self._active_id is not None:
            zone = self._tracked[self._active_id]
            if zone.end_ts is None:
                self._apply_bar_to_zone(zone, high, low, close, ts)
                if zone.end_ts is not None:
                    self._active_id = None

        self._highs.append(high)
        self._lows.append(low)

        if len(self._highs) < self._min_range_bars:
            return
        if not self._atr.ready or not self._long_atr.ready:
            return

        # Only attempt to confirm a new zone when none is active.
        if self._active_id is not None:
            return

        highs_list = list(self._highs)
        lows_list = list(self._lows)

        slope_high = _linear_slope(highs_list)
        slope_low = _linear_slope(lows_list)
        avg_slope = (abs(slope_high) + abs(slope_low)) / 2.0

        long_atr = self._long_atr.value
        if long_atr <= 0:
            return
        vol_ratio = self._atr.value / long_atr

        if avg_slope <= self._max_slope and vol_ratio <= self._volatility_threshold:
            range_high = max(highs_list)
            range_low = min(lows_list)
            range_size = range_high - range_low
            atr_value = self._atr.value
            range_atr_multiple = (
                range_size / atr_value if atr_value > 0 else 0.0
            )
            centroid = (range_high + range_low) / 2.0
            side: Literal["high", "low"] = "high" if centroid > close else "low"

            self._tracked.append(_TrackedZone(
                id=self._next_id,
                centroid=centroid,
                range_high=range_high,
                range_low=range_low,
                slope=avg_slope,
                bar_count=len(highs_list),
                duration_bars=len(highs_list),
                range_atr_multiple=range_atr_multiple,
                start_ts=ts,
                end_ts=None,
                last_touch_ts=ts,
                touch_count=0,
                side=side,
            ))
            self._active_id = len(self._tracked) - 1
            self._next_id += 1

    def _apply_bar_to_zone(
        self,
        zone: _TrackedZone,
        high: float,
        low: float,
        close: float,
        ts: int,
    ) -> None:
        atr_value = self._atr.value if self._atr.ready else 0.0

        if atr_value > 0:
            beyond = (
                close > zone.range_high + self._break_atr_multiple * atr_value
                or close < zone.range_low - self._break_atr_multiple * atr_value
            )
            if beyond:
                zone.end_ts = ts
                return

        # Touch: bar overlaps zone.
        if low <= zone.range_high and high >= zone.range_low:
            zone.touch_count += 1
            zone.last_touch_ts = ts
            zone.duration_bars += 1

        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - zone.last_touch_ts > idle_ns:
            zone.end_ts = zone.last_touch_ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for zone in self._tracked:
            strength = max(
                0.0, min(1.0, zone.duration_bars / self._min_range_bars),
            )
            out.append(KeyLevel(
                price=zone.centroid,
                strength=strength,
                start_ts=zone.start_ts,
                end_ts=zone.end_ts,
                source="consolidation_zone",
                bounce_count=max(1, zone.touch_count),
                zone_upper=zone.range_high,
                zone_lower=zone.range_low,
                meta=ConsolidationZoneMeta(
                    range_high=zone.range_high,
                    range_low=zone.range_low,
                    slope=zone.slope,
                    bar_count=zone.bar_count,
                    duration_bars=zone.duration_bars,
                    range_atr_multiple=zone.range_atr_multiple,
                    side=zone.side,
                    touch_count=zone.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._long_atr.reset()
        self._highs.clear()
        self._lows.clear()
        self._tracked.clear()
        self._active_id = None
        self._next_id = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
