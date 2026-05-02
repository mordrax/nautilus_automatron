"""FairValueGapDetector — three-bar imbalance gaps (lifecycle-tracked).

A Fair Value Gap (FVG) is a three-bar pattern where a gap exists between
``bar[i].low`` and ``bar[i-2].high`` (bullish) or ``bar[i].high`` and
``bar[i-2].low`` (bearish). Born at bar2 close. End: when fully filled
(``fill_percentage >= 1.0``) or aged out.

Single zoned level: ``zone_upper`` and ``zone_lower`` are the gap edges,
``price`` is the midpoint. ``meta.side`` (high/low) is derived from the gap
direction — bullish FVG sits below price (acts as support → side="low");
bearish sits above (resistance → side="high").
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import FairValueGapMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedFVG:
    id: int
    gap_side: Literal["bullish", "bearish"]
    centroid: float
    zone_upper: float
    zone_lower: float
    gap_size: float
    start_ts: int
    end_ts: int | None
    last_touch_ts: int
    touch_count: int
    deepest_fill: float
    side: Literal["high", "low"]


class FairValueGapDetector:

    def __init__(
        self,
        min_gap_atr_multiple: float = 0.5,
        max_idle_bars: int = 200,
        atr_period: int = 14,
    ) -> None:
        self._min_gap_atr_multiple = min_gap_atr_multiple
        self._max_idle_bars = max_idle_bars
        self._atr_period = atr_period

        self._atr = StreamingAtr(period=atr_period)
        self._recent_bars: deque[Bar] = deque(maxlen=3)

        self._tracked: list[_TrackedFVG] = []
        self._next_id: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

    @property
    def name(self) -> str:
        return "fair_value_gap"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period + 2

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

        # Update fill on existing gaps.
        for fvg in self._tracked:
            if fvg.end_ts is not None:
                continue
            self._apply_bar_to_gap(fvg, high, low, ts)

        self._recent_bars.append(bar)

        if len(self._recent_bars) < 3 or not self._atr.ready:
            return

        bar_0 = self._recent_bars[0]
        bar_2 = self._recent_bars[2]

        bar_0_high = float(bar_0.high)
        bar_0_low = float(bar_0.low)
        bar_2_high = float(bar_2.high)
        bar_2_low = float(bar_2.low)

        atr_val = self._atr.value
        if atr_val <= 0:
            return

        # Bullish FVG: bar2.low > bar0.high (gap sits below current price →
        # support → side="low").
        if bar_2_low > bar_0_high:
            gap_size = bar_2_low - bar_0_high
            if gap_size >= self._min_gap_atr_multiple * atr_val:
                self._emit_gap(
                    gap_side="bullish",
                    zone_upper=bar_2_low,
                    zone_lower=bar_0_high,
                    gap_size=gap_size,
                    ts=ts,
                )

        # Bearish FVG: bar2.high < bar0.low (gap sits above price → side="high").
        if bar_2_high < bar_0_low:
            gap_size = bar_0_low - bar_2_high
            if gap_size >= self._min_gap_atr_multiple * atr_val:
                self._emit_gap(
                    gap_side="bearish",
                    zone_upper=bar_0_low,
                    zone_lower=bar_2_high,
                    gap_size=gap_size,
                    ts=ts,
                )

    def _emit_gap(
        self,
        gap_side: Literal["bullish", "bearish"],
        zone_upper: float,
        zone_lower: float,
        gap_size: float,
        ts: int,
    ) -> None:
        side: Literal["high", "low"] = "low" if gap_side == "bullish" else "high"
        self._tracked.append(_TrackedFVG(
            id=self._next_id,
            gap_side=gap_side,
            centroid=(zone_upper + zone_lower) / 2.0,
            zone_upper=zone_upper,
            zone_lower=zone_lower,
            gap_size=gap_size,
            start_ts=ts,
            end_ts=None,
            last_touch_ts=ts,
            touch_count=0,
            deepest_fill=0.0,
            side=side,
        ))
        self._next_id += 1

    def _apply_bar_to_gap(
        self,
        fvg: _TrackedFVG,
        high: float,
        low: float,
        ts: int,
    ) -> None:
        if fvg.gap_side == "bullish":
            # Bullish FVG: price fills from above going down.
            if low < fvg.zone_upper:
                fill_depth = fvg.zone_upper - max(low, fvg.zone_lower)
                fvg.deepest_fill = max(fvg.deepest_fill, fill_depth)
                fvg.touch_count += 1
                fvg.last_touch_ts = ts
        else:
            # Bearish FVG: price fills from below going up.
            if high > fvg.zone_lower:
                fill_depth = min(high, fvg.zone_upper) - fvg.zone_lower
                fvg.deepest_fill = max(fvg.deepest_fill, fill_depth)
                fvg.touch_count += 1
                fvg.last_touch_ts = ts

        # Fully filled → end.
        if fvg.gap_size > 0 and fvg.deepest_fill >= fvg.gap_size:
            fvg.end_ts = ts
            return

        # Aged out.
        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - fvg.last_touch_ts > idle_ns:
            fvg.end_ts = fvg.last_touch_ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        atr_val = self._atr.value if self._atr.ready else 0.0
        for fvg in self._tracked:
            fill_pct = (
                fvg.deepest_fill / fvg.gap_size if fvg.gap_size > 0 else 0.0
            )
            fill_pct = max(0.0, min(1.0, fill_pct))
            base = (fvg.gap_size / atr_val) if atr_val > 0 else 0.0
            strength = max(0.0, min(1.0, base * (1.0 - fill_pct)))

            out.append(KeyLevel(
                price=fvg.centroid,
                strength=strength,
                start_ts=fvg.start_ts,
                end_ts=fvg.end_ts,
                source="fair_value_gap",
                bounce_count=max(1, fvg.touch_count),
                zone_upper=fvg.zone_upper,
                zone_lower=fvg.zone_lower,
                meta=FairValueGapMeta(
                    gap_side=fvg.gap_side,
                    gap_size=fvg.gap_size,
                    fill_percentage=fill_pct,
                    side=fvg.side,
                    touch_count=fvg.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._recent_bars.clear()
        self._tracked.clear()
        self._next_id = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
