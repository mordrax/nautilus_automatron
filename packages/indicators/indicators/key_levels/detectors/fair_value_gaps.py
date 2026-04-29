"""FairValueGapDetector — three-bar imbalance gaps.

A Fair Value Gap (FVG) is a three-bar pattern where a gap exists between
bar[i].low and bar[i-2].high (bullish) or bar[i].high and bar[i-2].low (bearish).
The gap represents an area of price imbalance that may act as support/resistance.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, FairValueGapMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedFVG:
    gap_upper: float
    gap_lower: float
    side: str  # "bullish" | "bearish"
    gap_size: float
    ts: int
    age: int
    deepest_fill: float  # how far price has filled into the gap


class FairValueGapDetector:

    def __init__(
        self,
        min_gap_atr_multiple: float = 0.5,
        max_age_bars: int = 200,
        atr_period: int = 14,
    ) -> None:
        self._min_gap_atr_multiple = min_gap_atr_multiple
        self._max_age_bars = max_age_bars
        self._atr_period = atr_period

        self._atr = StreamingAtr(period=atr_period)
        self._recent_bars: deque[Bar] = deque(maxlen=3)
        self._tracked: list[_TrackedFVG] = []

    @property
    def name(self) -> str:
        return "fair_value_gap"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period + 2

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)

        self._atr.update(high, low, close)

        # Age existing gaps
        for fvg in self._tracked:
            fvg.age += 1

        # Track fill on existing gaps
        for fvg in self._tracked:
            if fvg.side == "bullish":
                # Bullish FVG: gap is between gap_lower and gap_upper
                # Price fills from above going down
                if low < fvg.gap_upper:
                    fill_depth = fvg.gap_upper - max(low, fvg.gap_lower)
                    fvg.deepest_fill = max(fvg.deepest_fill, fill_depth)
            else:
                # Bearish FVG: price fills from below going up
                if high > fvg.gap_lower:
                    fill_depth = min(high, fvg.gap_upper) - fvg.gap_lower
                    fvg.deepest_fill = max(fvg.deepest_fill, fill_depth)

        # Expire fully filled or aged out
        self._tracked = [
            fvg for fvg in self._tracked
            if fvg.age < self._max_age_bars and fvg.deepest_fill < fvg.gap_size
        ]

        self._recent_bars.append(bar)

        # Need 3 bars to check for FVG
        if len(self._recent_bars) < 3 or not self._atr.ready:
            return

        bar_0 = self._recent_bars[0]  # bar[i-2]
        bar_2 = self._recent_bars[2]  # bar[i]

        bar_0_high = float(bar_0.high)
        bar_0_low = float(bar_0.low)
        bar_2_high = float(bar_2.high)
        bar_2_low = float(bar_2.low)

        atr_val = self._atr.value
        if atr_val <= 0:
            return

        # Bullish FVG: bar[i].low > bar[i-2].high
        if bar_2_low > bar_0_high:
            gap_size = bar_2_low - bar_0_high
            if gap_size >= self._min_gap_atr_multiple * atr_val:
                self._tracked.append(_TrackedFVG(
                    gap_upper=bar_2_low,
                    gap_lower=bar_0_high,
                    side="bullish",
                    gap_size=gap_size,
                    ts=bar.ts_event,
                    age=0,
                    deepest_fill=0.0,
                ))

        # Bearish FVG: bar[i].high < bar[i-2].low
        if bar_2_high < bar_0_low:
            gap_size = bar_0_low - bar_2_high
            if gap_size >= self._min_gap_atr_multiple * atr_val:
                self._tracked.append(_TrackedFVG(
                    gap_upper=bar_0_low,
                    gap_lower=bar_2_high,
                    side="bearish",
                    gap_size=gap_size,
                    ts=bar.ts_event,
                    age=0,
                    deepest_fill=0.0,
                ))

    def levels(self) -> list[KeyLevel]:
        result: list[KeyLevel] = []
        for fvg in self._tracked:
            fill_pct = fvg.deepest_fill / fvg.gap_size if fvg.gap_size > 0 else 0.0
            atr_val = self._atr.value
            raw_strength = (fvg.gap_size / atr_val * (1.0 - fill_pct)) if atr_val > 0 else 0.0
            strength = min(1.0, max(0.0, raw_strength))

            midpoint = (fvg.gap_upper + fvg.gap_lower) / 2.0
            result.append(KeyLevel(
                price=midpoint,
                strength=strength,
                bounce_count=1,
                first_seen_ts=fvg.ts,
                last_touched_ts=fvg.ts,
                zone_upper=fvg.gap_upper,
                zone_lower=fvg.gap_lower,
                source="fair_value_gap",
                meta=FairValueGapMeta(
                    side=fvg.side,
                    gap_size=fvg.gap_size,
                    fill_percentage=fill_pct,
                ),
            ))
        return result

    def reset(self) -> None:
        self._atr.reset()
        self._recent_bars.clear()
        self._tracked.clear()
