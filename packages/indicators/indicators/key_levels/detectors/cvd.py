"""CvdDetector -- Cumulative Volume Delta with pivot detection.

Estimates buy/sell volume per bar, tracks cumulative delta, and uses
SwingDetector on the CVD series to find pivots. The price at CVD pivot
bars becomes a key level, with divergence detection (price makes new
high but CVD doesn't, or vice versa).
"""

from __future__ import annotations

from collections import deque
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import CvdMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import Swing


def _detect_cvd_pivot(
    values: deque[float], indices: deque[int], timestamps: deque[int], period: int,
) -> Swing | None:
    """Detect a peak or trough in a 1-D series using a fractal-like approach.

    Checks if the center value is greater than (or less than) all
    surrounding values within the window.
    """
    window_size = 2 * period + 1
    if len(values) < window_size:
        return None

    center = period
    center_val = values[center]

    is_peak = all(center_val > values[j] for j in range(window_size) if j != center)
    is_trough = all(center_val < values[j] for j in range(window_size) if j != center)

    if is_peak:
        return Swing(
            price=center_val, bar_index=indices[center],
            ts=timestamps[center], side="high",
        )
    if is_trough:
        return Swing(
            price=center_val, bar_index=indices[center],
            ts=timestamps[center], side="low",
        )
    return None


def _estimate_buy_volume(open_: float, high: float, low: float, close: float, volume: float) -> float:
    """Estimate buy volume using close position within bar range.

    buy_vol = volume * (close - low) / (high - low)
    For bullish bars (close > open), close is near high -> more buy volume.
    For bearish bars (close < open), close is near low -> less buy volume.
    Doji (close == open): use same formula; if high == low -> 50/50.
    """
    bar_range = high - low
    if bar_range <= 0:
        return volume * 0.5

    return volume * (close - low) / bar_range


class CvdDetector:

    def __init__(
        self,
        swing_period: int = 5,
        atr_period: int = 14,
        max_pivots: int = 50,
    ) -> None:
        self._swing_period = swing_period
        self._atr = StreamingAtr(period=atr_period)
        self._max_pivots = max_pivots

        self._window_size = 2 * swing_period + 1
        self._cvd_window: deque[float] = deque(maxlen=self._window_size)
        self._idx_window: deque[int] = deque(maxlen=self._window_size)
        self._ts_window: deque[int] = deque(maxlen=self._window_size)

        self._bar_index: int = 0
        self._cvd: float = 0.0
        self._prices: list[float] = []
        self._cvd_values: list[float] = []
        self._timestamps: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "cvd"

    @property
    def warmup_bars(self) -> int:
        return self._window_size

    def update(self, bar: Bar) -> None:
        open_ = float(bar.open)
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        buy_vol = _estimate_buy_volume(open_, high, low, close, volume)
        sell_vol = volume - buy_vol
        delta = buy_vol - sell_vol
        self._cvd += delta

        self._prices.append(close)
        self._cvd_values.append(self._cvd)
        self._timestamps.append(ts)

        self._cvd_window.append(self._cvd)
        self._idx_window.append(self._bar_index)
        self._ts_window.append(ts)

        swing = _detect_cvd_pivot(
            self._cvd_window, self._idx_window, self._ts_window, self._swing_period,
        )

        if swing is not None:
            self._process_cvd_pivot(swing)

        self._bar_index += 1

    def _process_cvd_pivot(self, swing) -> None:
        """When a CVD pivot is confirmed, emit a level at the price of that bar."""
        idx = swing.bar_index
        if idx >= len(self._prices):
            return

        price = self._prices[idx]
        ts = self._timestamps[idx]
        cvd_val = self._cvd_values[idx]

        divergence = self._detect_divergence(swing, idx)

        atr = self._atr.value if self._atr.ready else 1.0

        # Stronger levels for divergence signals
        strength = 0.7 if divergence == "none" else 0.9

        level = KeyLevel(
            price=price,
            strength=strength,
            bounce_count=1,
            first_seen_ts=ts,
            last_touched_ts=ts,
            zone_upper=price + atr * 0.25,
            zone_lower=price - atr * 0.25,
            source="cvd",
            meta=CvdMeta(
                cvd_value=cvd_val,
                divergence=divergence,
            ),
        )

        self._levels.append(level)
        if len(self._levels) > self._max_pivots:
            self._levels.pop(0)

    def _detect_divergence(
        self, swing, idx: int,
    ) -> Literal["bullish", "bearish", "none"]:
        """Detect price-CVD divergence at pivot points.

        Bullish divergence: price makes lower low but CVD makes higher low
        Bearish divergence: price makes higher high but CVD makes lower high
        """
        if len(self._levels) < 1:
            return "none"

        # Find the most recent CVD pivot of the same side
        same_side_levels = [
            lvl for lvl in self._levels
            if (swing.side == "high" and lvl.meta.cvd_value > 0)
            or (swing.side == "low" and lvl.meta.cvd_value <= 0)
        ]
        if not same_side_levels:
            return "none"

        prev = same_side_levels[-1]
        curr_price = self._prices[idx]
        curr_cvd = self._cvd_values[idx]
        prev_price = prev.price
        prev_cvd = prev.meta.cvd_value

        if swing.side == "high":
            # Bearish divergence: price higher high, CVD lower high
            if curr_price > prev_price and curr_cvd < prev_cvd:
                return "bearish"
        else:
            # Bullish divergence: price lower low, CVD higher low
            if curr_price < prev_price and curr_cvd > prev_cvd:
                return "bullish"

        return "none"

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._cvd_window.clear()
        self._idx_window.clear()
        self._ts_window.clear()
        self._bar_index = 0
        self._cvd = 0.0
        self._prices.clear()
        self._cvd_values.clear()
        self._timestamps.clear()
        self._levels = []
