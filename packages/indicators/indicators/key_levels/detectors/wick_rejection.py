"""WickRejectionDetector — detect key levels from clustered long-wick bars.

A long wick indicates price rejection at a level. Multiple rejections in the
same price zone form a key level.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, WickRejectionMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.clustering import agglomerative_cluster


class WickRejectionDetector:

    def __init__(
        self,
        min_wick_ratio: float = 2.0,
        zone_atr_multiple: float = 1.0,
        atr_period: int = 14,
        min_rejections: int = 2,
        max_rejections: int = 200,
    ) -> None:
        self._min_wick_ratio = min_wick_ratio
        self._zone_atr_multiple = zone_atr_multiple
        self._min_rejections = min_rejections
        self._max_rejections = max_rejections

        self._atr = StreamingAtr(period=atr_period)

        self._rejection_prices: list[float] = []
        self._rejection_ratios: list[float] = []
        self._rejection_ts: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self):
        return "wick_rejection"

    @property
    def warmup_bars(self) -> int:
        return 1

    def update(self, bar: Bar) -> None:
        open_ = float(bar.open)
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low

        min_body = self._atr.value * 0.01 if self._atr.ready else 0.01

        # Lower wick rejection (support)
        if body > min_body and lower_wick / body >= self._min_wick_ratio:
            self._add_rejection(low, lower_wick / body, ts)
        elif body <= min_body and self._atr.ready and lower_wick > self._atr.value * 0.5:
            self._add_rejection(low, lower_wick / max(body, min_body), ts)

        # Upper wick rejection (resistance)
        if body > min_body and upper_wick / body >= self._min_wick_ratio:
            self._add_rejection(high, upper_wick / body, ts)
        elif body <= min_body and self._atr.ready and upper_wick > self._atr.value * 0.5:
            self._add_rejection(high, upper_wick / max(body, min_body), ts)

        if self._atr.ready:
            self._rebuild_levels()

    def _add_rejection(self, price: float, ratio: float, ts: int) -> None:
        self._rejection_prices.append(price)
        self._rejection_ratios.append(ratio)
        self._rejection_ts.append(ts)
        if len(self._rejection_prices) > self._max_rejections:
            self._rejection_prices.pop(0)
            self._rejection_ratios.pop(0)
            self._rejection_ts.pop(0)

    def _rebuild_levels(self) -> None:
        if len(self._rejection_prices) < self._min_rejections:
            self._levels = []
            return

        tolerance = self._atr.value * self._zone_atr_multiple
        if tolerance <= 0:
            self._levels = []
            return

        clusters = agglomerative_cluster(self._rejection_prices, tolerance)

        # Build sorted mapping for cluster-to-original mapping
        sorted_info = sorted(
            zip(self._rejection_prices, self._rejection_ratios, self._rejection_ts),
            key=lambda x: x[0],
        )

        max_count = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        info_idx = 0
        for members, centroid in clusters:
            if len(members) < self._min_rejections:
                info_idx += len(members)
                continue

            member_ratios: list[float] = []
            member_ts: list[int] = []
            for _ in members:
                if info_idx < len(sorted_info):
                    member_ratios.append(sorted_info[info_idx][1])
                    member_ts.append(sorted_info[info_idx][2])
                    info_idx += 1

            avg_ratio = sum(member_ratios) / len(member_ratios) if member_ratios else 0.0
            raw_strength = (len(members) / max_count) * min(1.0, avg_ratio / 5.0)
            strength = min(1.0, max(0.0, raw_strength))

            levels.append(KeyLevel(
                price=centroid,
                strength=strength,
                bounce_count=len(members),
                first_seen_ts=min(member_ts) if member_ts else 0,
                last_touched_ts=max(member_ts) if member_ts else 0,
                zone_upper=max(members),
                zone_lower=min(members),
                source="wick_rejection",
                meta=WickRejectionMeta(
                    rejection_count=len(members),
                    avg_wick_ratio=avg_ratio,
                ),
            ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._rejection_prices.clear()
        self._rejection_ratios.clear()
        self._rejection_ts.clear()
        self._levels = []
