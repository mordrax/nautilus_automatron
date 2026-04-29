"""SwingClusterDetector — detect key levels from clustered swing highs/lows.

Uses Williams fractal swing detection to find swing points, then clusters
nearby swings using agglomerative clustering to form key levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, SwingClusterMeta
from indicators.key_levels.shared.clustering import agglomerative_cluster
from indicators.key_levels.shared.swing import SwingDetector


class SwingClusterDetector:

    def __init__(
        self,
        period: int = 2,
        cluster_distance: float = 1.5,
        max_swings: int = 200,
    ) -> None:
        self._period = period
        self._cluster_distance = cluster_distance
        self._max_swings = max_swings

        self._swing_detector = SwingDetector(period=period)
        self._bar_index = 0

        self._swing_prices: list[float] = []
        self._swing_indices: list[int] = []
        self._swing_ts: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return self._swing_detector.warmup_bars

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        ts = bar.ts_event

        swing = self._swing_detector.update(high, low, self._bar_index, ts)
        self._bar_index += 1

        if swing is not None:
            self._swing_prices.append(swing.price)
            self._swing_indices.append(swing.bar_index)
            self._swing_ts.append(swing.ts)

            # Trim to max_swings
            if len(self._swing_prices) > self._max_swings:
                self._swing_prices.pop(0)
                self._swing_indices.pop(0)
                self._swing_ts.pop(0)

            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        if not self._swing_prices:
            self._levels = []
            return

        clusters = agglomerative_cluster(self._swing_prices, self._cluster_distance)

        # Map sorted prices back to indices/timestamps
        sorted_info = sorted(
            zip(self._swing_prices, self._swing_indices, self._swing_ts),
            key=lambda x: x[0],
        )

        max_count = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        info_idx = 0
        for members, centroid in clusters:
            member_indices: list[int] = []
            member_ts: list[int] = []
            for _ in members:
                if info_idx < len(sorted_info):
                    member_indices.append(sorted_info[info_idx][1])
                    member_ts.append(sorted_info[info_idx][2])
                    info_idx += 1

            strength = min(1.0, max(0.0, len(members) / max_count))

            levels.append(KeyLevel(
                price=centroid,
                strength=strength,
                bounce_count=len(members),
                first_seen_ts=min(member_ts) if member_ts else 0,
                last_touched_ts=max(member_ts) if member_ts else 0,
                zone_upper=max(members),
                zone_lower=min(members),
                source="swing_cluster",
                meta=SwingClusterMeta(
                    cluster_radius=self._cluster_distance,
                    pivot_indices=tuple(member_indices),
                ),
            ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._swing_detector.reset()
        self._bar_index = 0
        self._swing_prices.clear()
        self._swing_indices.clear()
        self._swing_ts.clear()
        self._levels = []
