"""PriceGapDetector — between-bar price gaps (lifecycle-tracked).

A price gap occurs when ``bar.low > prev.high`` (gap up) or
``bar.high < prev.low`` (gap down). Classified by volume relative to the
rolling average — breakaway (high vol), runaway (mid vol), exhaustion
(low vol), common (default). End: filled or aged out.

Emitted as a SINGLE zoned level (deviates from original spec which emitted
two separate edge levels) so the level shape matches the rest of the suite.
``zone_upper`` / ``zone_lower`` are the gap edges; ``price`` is the midpoint.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PriceGapMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedGap:
    id: int
    direction: Literal["up", "down"]
    centroid: float
    zone_upper: float
    zone_lower: float
    gap_type: Literal["breakaway", "runaway", "exhaustion", "common"]
    gap_size: float
    start_ts: int
    end_ts: int | None
    last_touch_ts: int
    touch_count: int
    deepest_fill: float
    level_type: Literal["upper", "lower"]
    side: Literal["high", "low"]


class PriceGapDetector:

    def __init__(
        self,
        min_gap_atr_multiple: float = 0.5,
        volume_period: int = 20,
        max_idle_bars: int = 200,
        atr_period: int = 14,
    ) -> None:
        self._min_gap_atr_multiple = min_gap_atr_multiple
        self._volume_period = volume_period
        self._max_idle_bars = max_idle_bars
        self._atr_period = atr_period

        self._atr = StreamingAtr(period=atr_period)
        self._volumes: deque[float] = deque(maxlen=volume_period)
        self._prev_bar: Bar | None = None

        self._tracked: list[_TrackedGap] = []
        self._next_id: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

    @property
    def name(self) -> str:
        return "price_gap"

    @property
    def warmup_bars(self) -> int:
        return max(self._atr_period, self._volume_period) + 1

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

        # Per-bar lifecycle on existing gaps.
        for gap in self._tracked:
            if gap.end_ts is not None:
                continue
            self._apply_bar_to_gap(gap, high, low, ts)

        # Detect new gap.
        if self._prev_bar is not None and self._atr.ready:
            prev_high = float(self._prev_bar.high)
            prev_low = float(self._prev_bar.low)
            atr_val = self._atr.value

            if atr_val > 0:
                if low > prev_high:
                    gap_size = low - prev_high
                    if gap_size >= self._min_gap_atr_multiple * atr_val:
                        self._emit_gap(
                            direction="up",
                            zone_upper=low,
                            zone_lower=prev_high,
                            gap_size=gap_size,
                            volume=volume,
                            ts=ts,
                        )
                if high < prev_low:
                    gap_size = prev_low - high
                    if gap_size >= self._min_gap_atr_multiple * atr_val:
                        self._emit_gap(
                            direction="down",
                            zone_upper=prev_low,
                            zone_lower=high,
                            gap_size=gap_size,
                            volume=volume,
                            ts=ts,
                        )

        self._volumes.append(volume)
        self._prev_bar = bar

    def _emit_gap(
        self,
        direction: Literal["up", "down"],
        zone_upper: float,
        zone_lower: float,
        gap_size: float,
        volume: float,
        ts: int,
    ) -> None:
        gap_type = self._classify_gap(volume)
        # Gap up sits below current price → support → side="low".
        # Gap down sits above price → resistance → side="high".
        side: Literal["high", "low"] = "low" if direction == "up" else "high"
        # ``level_type`` is preserved from the original spec for compatibility,
        # but as a single-zone level we always tag "upper" (the gap is the
        # whole zone). Could be widened later if the consumer needs it.
        level_type: Literal["upper", "lower"] = "upper"

        self._tracked.append(_TrackedGap(
            id=self._next_id,
            direction=direction,
            centroid=(zone_upper + zone_lower) / 2.0,
            zone_upper=zone_upper,
            zone_lower=zone_lower,
            gap_type=gap_type,
            gap_size=gap_size,
            start_ts=ts,
            end_ts=None,
            last_touch_ts=ts,
            touch_count=0,
            deepest_fill=0.0,
            level_type=level_type,
            side=side,
        ))
        self._next_id += 1

    def _apply_bar_to_gap(
        self,
        gap: _TrackedGap,
        high: float,
        low: float,
        ts: int,
    ) -> None:
        if gap.direction == "up":
            if low < gap.zone_upper:
                fill_depth = gap.zone_upper - max(low, gap.zone_lower)
                gap.deepest_fill = max(gap.deepest_fill, fill_depth)
                gap.touch_count += 1
                gap.last_touch_ts = ts
        else:
            if high > gap.zone_lower:
                fill_depth = min(high, gap.zone_upper) - gap.zone_lower
                gap.deepest_fill = max(gap.deepest_fill, fill_depth)
                gap.touch_count += 1
                gap.last_touch_ts = ts

        if gap.gap_size > 0 and gap.deepest_fill >= gap.gap_size:
            gap.end_ts = ts
            return

        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - gap.last_touch_ts > idle_ns:
            gap.end_ts = gap.last_touch_ts

    def _classify_gap(
        self, volume: float,
    ) -> Literal["breakaway", "runaway", "exhaustion", "common"]:
        if len(self._volumes) < self._volume_period:
            return "common"
        avg_vol = sum(self._volumes) / len(self._volumes)
        if avg_vol <= 0:
            return "common"
        ratio = volume / avg_vol
        if ratio > 1.5:
            return "breakaway"
        if ratio < 0.5:
            return "exhaustion"
        return "common"

    def _gap_strength(self, gap_type: str) -> float:
        if gap_type == "breakaway":
            return 1.0
        if gap_type == "exhaustion":
            return 0.3
        return 0.5

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for gap in self._tracked:
            fill_pct = (
                gap.deepest_fill / gap.gap_size if gap.gap_size > 0 else 0.0
            )
            fill_pct = max(0.0, min(1.0, fill_pct))
            base = self._gap_strength(gap.gap_type)
            strength = max(0.0, min(1.0, base * (1.0 - fill_pct)))

            out.append(KeyLevel(
                price=gap.centroid,
                strength=strength,
                start_ts=gap.start_ts,
                end_ts=gap.end_ts,
                source="price_gap",
                bounce_count=max(1, gap.touch_count),
                zone_upper=gap.zone_upper,
                zone_lower=gap.zone_lower,
                meta=PriceGapMeta(
                    gap_type=gap.gap_type,
                    gap_size=gap.gap_size,
                    fill_percentage=fill_pct,
                    level_type=gap.level_type,
                    side=gap.side,
                    touch_count=gap.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._volumes.clear()
        self._prev_bar = None
        self._tracked.clear()
        self._next_id = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
