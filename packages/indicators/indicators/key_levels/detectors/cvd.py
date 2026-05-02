"""CvdDetector — Cumulative Volume Delta pivot levels (lifecycle-tracked).

Estimates buy/sell volume per bar, tracks cumulative delta, and runs a
fractal-like pivot detector over the CVD series. Each confirmed CVD pivot
emits a level at the *price* of the pivot bar, with divergence detection
(price makes a new high but CVD doesn't, or vice versa).

A level is born when its CVD pivot is confirmed and lives until:

- a sustained close beyond the level for `break_consecutive_bars` bars (break)
- aged-out (no touch for `max_idle_bars` bars)

`bounce_count` increments on swing-pivot touches; `touch_count` on bar-level
overlaps with the tolerance band around the centroid.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import CvdMeta, KeyLevel
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
    cvd_value: float
    divergence: Literal["bullish", "bearish", "none"]
    atr_at_emit: float


def _detect_cvd_pivot(
    values: deque[float],
    indices: deque[int],
    timestamps: deque[int],
    period: int,
) -> Swing | None:
    """Detect a CVD-series pivot using a fractal-like center comparison."""
    window_size = 2 * period + 1
    if len(values) < window_size:
        return None
    center = period
    center_val = values[center]
    is_peak = all(center_val > values[j] for j in range(window_size) if j != center)
    is_trough = all(center_val < values[j] for j in range(window_size) if j != center)
    if is_peak:
        return Swing(
            price=center_val,
            bar_index=indices[center],
            ts=timestamps[center],
            side="high",
        )
    if is_trough:
        return Swing(
            price=center_val,
            bar_index=indices[center],
            ts=timestamps[center],
            side="low",
        )
    return None


def _estimate_buy_volume(
    open_: float, high: float, low: float, close: float, volume: float,
) -> float:
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
        price_swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._swing_period = swing_period
        self._max_pivots = max_pivots
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._atr = StreamingAtr(period=atr_period)
        # Price swing detector for bounce_count attachment.
        self._price_swing_detector = SwingDetector(period=price_swing_period)

        self._window_size = 2 * swing_period + 1
        self._cvd_window: deque[float] = deque(maxlen=self._window_size)
        self._idx_window: deque[int] = deque(maxlen=self._window_size)
        self._ts_window: deque[int] = deque(maxlen=self._window_size)

        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None
        self._cvd: float = 0.0

        # Per-bar history for pivot price/ts/cvd lookup.
        self._prices: list[float] = []
        self._cvd_values: list[float] = []
        self._timestamps: list[int] = []

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "cvd"

    @property
    def warmup_bars(self) -> int:
        return self._window_size

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        open_ = float(bar.open)
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

        buy_vol = _estimate_buy_volume(open_, high, low, close, volume)
        sell_vol = volume - buy_vol
        self._cvd += buy_vol - sell_vol

        self._prices.append(close)
        self._cvd_values.append(self._cvd)
        self._timestamps.append(ts)

        self._cvd_window.append(self._cvd)
        self._idx_window.append(self._bar_index)
        self._ts_window.append(ts)

        # Price-side swing for bounce_count attachment.
        price_swing = self._price_swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )

        cvd_pivot = _detect_cvd_pivot(
            self._cvd_window, self._idx_window, self._ts_window, self._swing_period,
        )

        self._bar_index += 1

        atr_ready = self._atr.ready
        atr_value = self._atr.value if atr_ready else 1.0
        tolerance = 0.25 * atr_value

        # Per-bar lifecycle on active levels.
        for lvl in self._tracked:
            if lvl.end_ts is None:
                self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # Attach price swing to closest same-side active level.
        if price_swing is not None:
            best: _TrackedLevel | None = None
            best_dist = tolerance
            for lvl in self._tracked:
                if lvl.end_ts is not None or lvl.side != price_swing.side:
                    continue
                dist = abs(price_swing.price - lvl.centroid)
                if dist <= best_dist:
                    best = lvl
                    best_dist = dist
            if best is not None:
                best.bounce_count += 1
                best.last_touch_ts = price_swing.ts

        if cvd_pivot is not None:
            self._process_cvd_pivot(cvd_pivot, atr_value)

    def _process_cvd_pivot(self, swing: Swing, atr_value: float) -> None:
        idx = swing.bar_index
        if idx >= len(self._prices):
            return
        price = self._prices[idx]
        ts = self._timestamps[idx]
        cvd_val = self._cvd_values[idx]

        divergence = self._detect_divergence(swing, idx)

        side: Literal["high", "low"] = swing.side

        new_idx = len(self._tracked)
        self._tracked.append(_TrackedLevel(
            id=self._next_id,
            side=side,
            centroid=price,
            start_ts=ts,
            end_ts=None,
            bounce_count=0,
            touch_count=0,
            last_touch_ts=ts,
            bars_through=0,
            cvd_value=cvd_val,
            divergence=divergence,
            atr_at_emit=atr_value,
        ))
        self._next_id += 1

        # Cap retained levels (oldest evicted, finalized at current ts).
        if len(self._tracked) > self._max_pivots:
            # Find oldest still-active level and finalize it.
            for lvl in self._tracked:
                if lvl.end_ts is None and lvl.id < self._tracked[new_idx].id:
                    lvl.end_ts = ts
                    break

    def _detect_divergence(
        self, swing: Swing, idx: int,
    ) -> Literal["bullish", "bearish", "none"]:
        if not self._tracked:
            return "none"

        # Find the most recent same-side active or finalized CVD-pivot level.
        same_side = [lvl for lvl in self._tracked if lvl.side == swing.side]
        if not same_side:
            return "none"

        prev = same_side[-1]
        curr_price = self._prices[idx]
        curr_cvd = self._cvd_values[idx]
        prev_price = prev.centroid
        prev_cvd = prev.cvd_value

        if swing.side == "high":
            if curr_price > prev_price and curr_cvd < prev_cvd:
                return "bearish"
        else:
            if curr_price < prev_price and curr_cvd > prev_cvd:
                return "bullish"
        return "none"

    def _apply_bar_to_level(
        self,
        lvl: _TrackedLevel,
        high: float,
        low: float,
        close: float,
        ts: int,
        tolerance: float,
    ) -> None:
        atr_value = self._atr.value if self._atr.ready else 1.0
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
            base = 0.9 if lvl.divergence != "none" else 0.7
            strength = max(0.0, min(1.0, base * decay))

            zone_half = 0.25 * lvl.atr_at_emit

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="cvd",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid + zone_half,
                zone_lower=lvl.centroid - zone_half,
                meta=CvdMeta(
                    cvd_value=lvl.cvd_value,
                    divergence=lvl.divergence,
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._price_swing_detector.reset()
        self._cvd_window.clear()
        self._idx_window.clear()
        self._ts_window.clear()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._cvd = 0.0
        self._prices.clear()
        self._cvd_values.clear()
        self._timestamps.clear()
        self._tracked.clear()
        self._next_id = 0
