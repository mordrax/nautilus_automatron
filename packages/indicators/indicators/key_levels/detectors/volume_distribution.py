"""VolumeDistributionDetector -- context-aware volume profile.

Uses SwingDetector to identify structural contexts (consolidation between
swings, peak/trough regions), then computes volume distribution within each
context to find the highest-volume price zone.
"""

from __future__ import annotations

from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, VolumeDistributionMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import Swing, SwingDetector


def _classify_context(
    prev_swing: Swing | None, curr_swing: Swing | None,
) -> Literal["consolidation", "peak", "trough", "range"]:
    """Classify the structural context between two swings."""
    if prev_swing is None or curr_swing is None:
        return "range"
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
    ) -> None:
        self._swing_period = swing_period
        self._min_context_bars = min_context_bars
        self._bin_count = bin_count
        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)

        self._bar_index: int = 0
        # Buffer bars as (high, low, close, volume, ts)
        self._bars: list[tuple[float, float, float, float, int]] = []
        self._swings: list[Swing] = []
        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "volume_distribution"

    @property
    def warmup_bars(self) -> int:
        return self._swing_detector.warmup_bars + self._min_context_bars

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        self._atr.update(high, low, close)
        self._bars.append((high, low, close, volume, ts))

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        if swing is not None:
            self._swings.append(swing)

        self._bar_index += 1

        if self._atr.ready and len(self._swings) >= 2:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        levels: list[KeyLevel] = []
        atr = self._atr.value

        for i in range(1, len(self._swings)):
            prev_swing = self._swings[i - 1]
            curr_swing = self._swings[i]

            start_idx = prev_swing.bar_index
            end_idx = curr_swing.bar_index

            # Clamp to available bars
            if start_idx < 0:
                start_idx = 0
            if end_idx >= len(self._bars):
                end_idx = len(self._bars) - 1

            context_bars = self._bars[start_idx : end_idx + 1]
            if len(context_bars) < self._min_context_bars:
                continue

            context = _classify_context(prev_swing, curr_swing)
            level = self._volume_poc_for_context(context_bars, context, atr)
            if level is not None:
                levels.append(level)

        self._levels = levels

    def _volume_poc_for_context(
        self,
        context_bars: list[tuple[float, float, float, float, int]],
        context: Literal["consolidation", "peak", "trough", "range"],
        atr: float,
    ) -> KeyLevel | None:
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

        first_ts = context_bars[0][4]
        last_ts = context_bars[-1][4]

        return KeyLevel(
            price=poc_price,
            strength=min(1.0, concentration * self._bin_count),
            bounce_count=1,
            first_seen_ts=first_ts,
            last_touched_ts=last_ts,
            zone_upper=poc_price + atr * 0.25,
            zone_lower=poc_price - atr * 0.25,
            source="volume_distribution",
            meta=VolumeDistributionMeta(
                context=context,
                volume_concentration=concentration,
                context_bar_count=len(context_bars),
            ),
        )

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._swing_detector.reset()
        self._bar_index = 0
        self._bars.clear()
        self._swings.clear()
        self._levels = []
