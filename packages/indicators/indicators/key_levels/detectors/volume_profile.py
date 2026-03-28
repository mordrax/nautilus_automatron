"""VolumeProfileDetector — detect key levels from volume distribution across price bins.

Discretizes the price range into bins over a lookback window, accumulates volume
per bin, and identifies POC (Point of Control), Value Area High/Low, HVN (High
Volume Nodes), and LVN (Low Volume Nodes).
"""

from __future__ import annotations

from collections import deque

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, VolumeProfileMeta
from indicators.key_levels.shared.atr import StreamingAtr


class VolumeProfileDetector:

    def __init__(
        self,
        lookback_bars: int = 50,
        bin_count: int = 50,
        value_area_pct: float = 0.7,
        atr_period: int = 14,
    ) -> None:
        self._lookback_bars = lookback_bars
        self._bin_count = bin_count
        self._value_area_pct = value_area_pct
        self._atr = StreamingAtr(period=atr_period)

        self._bar_window: deque[tuple[float, float, float, float, float, int]] = deque(
            maxlen=lookback_bars
        )  # (open, high, low, close, volume, ts)
        self._bar_count: int = 0
        self._levels: list[KeyLevel] = []

    @property
    def name(self):
        return "volume_profile"

    @property
    def warmup_bars(self) -> int:
        return self._lookback_bars

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        open_ = float(bar.open)
        volume = float(bar.volume)
        ts = bar.ts_event

        self._atr.update(high, low, close)
        self._bar_window.append((open_, high, low, close, volume, ts))
        self._bar_count += 1

        if self._bar_count >= self._lookback_bars and self._atr.ready:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        if len(self._bar_window) < 2:
            self._levels = []
            return

        # Find price range across the window
        all_highs = [b[1] for b in self._bar_window]
        all_lows = [b[2] for b in self._bar_window]
        price_min = min(all_lows)
        price_max = max(all_highs)
        price_range = price_max - price_min

        if price_range <= 0:
            self._levels = []
            return

        bin_size = price_range / self._bin_count
        volume_bins = [0.0] * self._bin_count

        # Accumulate volume per bin
        for _open, high, low, _close, volume, _ts in self._bar_window:
            if volume <= 0 or high <= low:
                continue
            bar_range = high - low
            for bi in range(self._bin_count):
                bin_low = price_min + bi * bin_size
                bin_high = bin_low + bin_size
                # Overlap between bar range [low, high] and bin [bin_low, bin_high]
                overlap_low = max(low, bin_low)
                overlap_high = min(high, bin_high)
                if overlap_high > overlap_low:
                    proportion = (overlap_high - overlap_low) / bar_range
                    volume_bins[bi] += volume * proportion

        total_volume = sum(volume_bins)
        if total_volume <= 0:
            self._levels = []
            return

        # Get timestamps for level metadata
        first_ts = self._bar_window[0][5]
        last_ts = self._bar_window[-1][5]
        atr = self._atr.value

        levels: list[KeyLevel] = []

        # POC: bin with maximum volume
        poc_idx = max(range(self._bin_count), key=lambda i: volume_bins[i])
        poc_price = price_min + (poc_idx + 0.5) * bin_size
        poc_volume = volume_bins[poc_idx]

        levels.append(KeyLevel(
            price=poc_price,
            strength=1.0,
            bounce_count=1,
            first_seen_ts=first_ts,
            last_touched_ts=last_ts,
            zone_upper=poc_price + atr * 0.25,
            zone_lower=poc_price - atr * 0.25,
            source="volume_profile",
            meta=VolumeProfileMeta(
                volume_concentration=poc_volume / total_volume,
                node_type="poc",
                bin_volume=poc_volume,
            ),
        ))

        # Value Area: expand from POC until value_area_pct of total volume
        va_volume = poc_volume
        va_low_idx = poc_idx
        va_high_idx = poc_idx
        target_volume = total_volume * self._value_area_pct

        while va_volume < target_volume and (va_low_idx > 0 or va_high_idx < self._bin_count - 1):
            expand_low = volume_bins[va_low_idx - 1] if va_low_idx > 0 else -1.0
            expand_high = volume_bins[va_high_idx + 1] if va_high_idx < self._bin_count - 1 else -1.0

            if expand_high >= expand_low:
                va_high_idx += 1
                va_volume += volume_bins[va_high_idx]
            else:
                va_low_idx -= 1
                va_volume += volume_bins[va_low_idx]

        va_high_price = price_min + (va_high_idx + 1) * bin_size
        va_low_price = price_min + va_low_idx * bin_size

        levels.append(KeyLevel(
            price=va_high_price,
            strength=0.8,
            bounce_count=1,
            first_seen_ts=first_ts,
            last_touched_ts=last_ts,
            zone_upper=va_high_price + atr * 0.25,
            zone_lower=va_high_price - atr * 0.25,
            source="volume_profile",
            meta=VolumeProfileMeta(
                volume_concentration=va_volume / total_volume,
                node_type="va_high",
                bin_volume=volume_bins[va_high_idx],
            ),
        ))

        levels.append(KeyLevel(
            price=va_low_price,
            strength=0.8,
            bounce_count=1,
            first_seen_ts=first_ts,
            last_touched_ts=last_ts,
            zone_upper=va_low_price + atr * 0.25,
            zone_lower=va_low_price - atr * 0.25,
            source="volume_profile",
            meta=VolumeProfileMeta(
                volume_concentration=va_volume / total_volume,
                node_type="va_low",
                bin_volume=volume_bins[va_low_idx],
            ),
        ))

        # HVN: local maxima in volume histogram
        for i in range(1, self._bin_count - 1):
            if i == poc_idx:
                continue  # POC already captured
            if volume_bins[i] > volume_bins[i - 1] and volume_bins[i] > volume_bins[i + 1]:
                node_price = price_min + (i + 0.5) * bin_size
                volume_ratio = volume_bins[i] / poc_volume if poc_volume > 0 else 0.0
                levels.append(KeyLevel(
                    price=node_price,
                    strength=min(1.0, volume_ratio),
                    bounce_count=1,
                    first_seen_ts=first_ts,
                    last_touched_ts=last_ts,
                    zone_upper=node_price + atr * 0.25,
                    zone_lower=node_price - atr * 0.25,
                    source="volume_profile",
                    meta=VolumeProfileMeta(
                        volume_concentration=volume_bins[i] / total_volume,
                        node_type="hvn",
                        bin_volume=volume_bins[i],
                    ),
                ))

        # LVN: local minima in volume histogram
        for i in range(1, self._bin_count - 1):
            if volume_bins[i] < volume_bins[i - 1] and volume_bins[i] < volume_bins[i + 1]:
                node_price = price_min + (i + 0.5) * bin_size
                levels.append(KeyLevel(
                    price=node_price,
                    strength=0.3,
                    bounce_count=1,
                    first_seen_ts=first_ts,
                    last_touched_ts=last_ts,
                    zone_upper=node_price + atr * 0.25,
                    zone_lower=node_price - atr * 0.25,
                    source="volume_profile",
                    meta=VolumeProfileMeta(
                        volume_concentration=volume_bins[i] / total_volume,
                        node_type="lvn",
                        bin_volume=volume_bins[i],
                    ),
                ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._bar_window.clear()
        self._bar_count = 0
        self._levels = []
