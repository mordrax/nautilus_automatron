"""PriceGapDetector — inter-bar price gaps.

A price gap occurs when current bar.low > prev bar.high (gap up) or
current bar.high < prev bar.low (gap down). Gaps are classified by
volume relative to the rolling average.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PriceGapMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedGap:
    upper: float  # upper edge of the gap
    lower: float  # lower edge of the gap
    side: str  # "up" | "down"
    gap_type: str  # "breakaway" | "runaway" | "exhaustion" | "common"
    gap_size: float
    ts: int
    age: int
    deepest_fill: float


class PriceGapDetector:

    def __init__(
        self,
        min_gap_atr_multiple: float = 0.5,
        volume_period: int = 20,
        max_age_bars: int = 200,
        atr_period: int = 14,
    ) -> None:
        self._min_gap_atr_multiple = min_gap_atr_multiple
        self._volume_period = volume_period
        self._max_age_bars = max_age_bars
        self._atr_period = atr_period

        self._atr = StreamingAtr(period=atr_period)
        self._volumes: deque[float] = deque(maxlen=volume_period)
        self._prev_bar: Bar | None = None
        self._tracked: list[_TrackedGap] = []

    @property
    def name(self) -> str:
        return "price_gap"

    @property
    def warmup_bars(self) -> int:
        return max(self._atr_period, self._volume_period) + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        # Age and fill-track existing gaps
        for gap in self._tracked:
            gap.age += 1
            if gap.side == "up":
                # Gap up: price fills from above going down
                if low < gap.upper:
                    fill_depth = gap.upper - max(low, gap.lower)
                    gap.deepest_fill = max(gap.deepest_fill, fill_depth)
            else:
                # Gap down: price fills from below going up
                if high > gap.lower:
                    fill_depth = min(high, gap.upper) - gap.lower
                    gap.deepest_fill = max(gap.deepest_fill, fill_depth)

        # Expire fully filled or aged out
        self._tracked = [
            g for g in self._tracked
            if g.age < self._max_age_bars and g.deepest_fill < g.gap_size
        ]

        # Detect new gaps
        if self._prev_bar is not None and self._atr.ready:
            prev_high = float(self._prev_bar.high)
            prev_low = float(self._prev_bar.low)
            atr_val = self._atr.value

            if atr_val > 0:
                # Gap up: current low > previous high
                if low > prev_high:
                    gap_size = low - prev_high
                    if gap_size >= self._min_gap_atr_multiple * atr_val:
                        gap_type = self._classify_gap(volume)
                        self._tracked.append(_TrackedGap(
                            upper=low,
                            lower=prev_high,
                            side="up",
                            gap_type=gap_type,
                            gap_size=gap_size,
                            ts=ts,
                            age=0,
                            deepest_fill=0.0,
                        ))

                # Gap down: current high < previous low
                if high < prev_low:
                    gap_size = prev_low - high
                    if gap_size >= self._min_gap_atr_multiple * atr_val:
                        gap_type = self._classify_gap(volume)
                        self._tracked.append(_TrackedGap(
                            upper=prev_low,
                            lower=high,
                            side="down",
                            gap_type=gap_type,
                            gap_size=gap_size,
                            ts=ts,
                            age=0,
                            deepest_fill=0.0,
                        ))

        self._volumes.append(volume)
        self._prev_bar = bar

    def _classify_gap(self, volume: float) -> str:
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
        return 0.5  # common or runaway

    def levels(self) -> list[KeyLevel]:
        result: list[KeyLevel] = []
        for gap in self._tracked:
            fill_pct = gap.deepest_fill / gap.gap_size if gap.gap_size > 0 else 0.0
            base_strength = self._gap_strength(gap.gap_type)
            strength = min(1.0, max(0.0, base_strength * (1.0 - fill_pct)))

            # Emit two levels: upper edge and lower edge
            for level_type, price in [("upper", gap.upper), ("lower", gap.lower)]:
                result.append(KeyLevel(
                    price=price,
                    strength=strength,
                    bounce_count=1,
                    first_seen_ts=gap.ts,
                    last_touched_ts=gap.ts,
                    zone_upper=gap.upper,
                    zone_lower=gap.lower,
                    source="price_gap",
                    meta=PriceGapMeta(
                        gap_type=gap.gap_type,
                        gap_size=gap.gap_size,
                        fill_percentage=fill_pct,
                        level_type=level_type,
                    ),
                ))
        return result

    def reset(self) -> None:
        self._atr.reset()
        self._volumes.clear()
        self._prev_bar = None
        self._tracked.clear()
