"""EqualHighsLowsDetector — detect levels where multiple swing highs or lows
touch approximately the same price.

Uses SwingDetector to find fractal pivots, then groups swing highs and swing
lows separately by ATR-based tolerance. Groups with >= min_touches become levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import EqualHighsLowsMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.clustering import agglomerative_cluster
from indicators.key_levels.shared.swing import SwingDetector


class EqualHighsLowsDetector:

    def __init__(
        self,
        period: int = 2,
        tolerance_atr_multiple: float = 0.5,
        atr_period: int = 14,
        min_touches: int = 2,
        max_swings: int = 100,
    ) -> None:
        self._period = period
        self._tolerance_atr_multiple = tolerance_atr_multiple
        self._min_touches = min_touches
        self._max_swings = max_swings

        self._swing_detector = SwingDetector(period=period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0

        self._swing_high_prices: list[float] = []
        self._swing_high_ts: list[int] = []
        self._swing_low_prices: list[float] = []
        self._swing_low_ts: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self):
        return "equal_highs_lows"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._period + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )

        if swing is not None:
            if swing.side == "high":
                self._swing_high_prices.append(swing.price)
                self._swing_high_ts.append(swing.ts)
                if len(self._swing_high_prices) > self._max_swings:
                    self._swing_high_prices.pop(0)
                    self._swing_high_ts.pop(0)
            else:
                self._swing_low_prices.append(swing.price)
                self._swing_low_ts.append(swing.ts)
                if len(self._swing_low_prices) > self._max_swings:
                    self._swing_low_prices.pop(0)
                    self._swing_low_ts.pop(0)

        self._bar_index += 1

        if self._atr.ready:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        tolerance = self._atr.value * self._tolerance_atr_multiple
        if tolerance <= 0:
            self._levels = []
            return

        levels: list[KeyLevel] = []
        levels.extend(self._cluster_side(self._swing_high_prices, self._swing_high_ts, "high", tolerance))
        levels.extend(self._cluster_side(self._swing_low_prices, self._swing_low_ts, "low", tolerance))
        self._levels = levels

    def _cluster_side(
        self, prices: list[float], timestamps: list[int], side: str, tolerance: float,
    ) -> list[KeyLevel]:
        if len(prices) < self._min_touches:
            return []

        clusters = agglomerative_cluster(prices, tolerance)

        # Build a mapping from sorted prices back to their timestamps
        # agglomerative_cluster sorts values, so we need to match them back
        sorted_price_ts = sorted(zip(prices, timestamps), key=lambda x: x[0])

        max_touches = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        member_idx = 0
        for members, centroid in clusters:
            if len(members) < self._min_touches:
                member_idx += len(members)
                continue

            member_ts: list[int] = []
            member_prices_actual: list[float] = []
            for _ in members:
                if member_idx < len(sorted_price_ts):
                    member_prices_actual.append(sorted_price_ts[member_idx][0])
                    member_ts.append(sorted_price_ts[member_idx][1])
                    member_idx += 1

            strength = len(members) / max_touches if max_touches > 0 else 0.0

            levels.append(KeyLevel(
                price=centroid,
                strength=min(1.0, strength),
                bounce_count=len(members),
                first_seen_ts=min(member_ts) if member_ts else 0,
                last_touched_ts=max(member_ts) if member_ts else 0,
                zone_upper=max(members),
                zone_lower=min(members),
                source="equal_highs_lows",
                meta=EqualHighsLowsMeta(
                    touch_prices=tuple(members),
                    side=side,
                ),
            ))

        return levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._levels = []
        self._swing_high_prices.clear()
        self._swing_high_ts.clear()
        self._swing_low_prices.clear()
        self._swing_low_ts.clear()
