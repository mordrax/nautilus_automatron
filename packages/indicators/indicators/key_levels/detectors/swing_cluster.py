"""SwingClusterDetector — detect levels from clustered swing highs and lows.

Uses SwingDetector to find fractal pivots, then clusters nearby swing points
using agglomerative clustering. Each cluster becomes a key level whose
strength scales with bounce count.
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
        cluster_distance: float = 2.0,
        max_swings: int = 200,
    ) -> None:
        self._period = period
        self._cluster_distance = cluster_distance
        self._max_swings = max_swings

        self._swing_detector = SwingDetector(period=period)
        self._bar_index: int = 0

        self._swing_prices: list[float] = []
        self._swing_indices: list[int] = []
        self._swing_ts: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._period + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        ts = bar.ts_event

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )

        if swing is not None:
            self._swing_prices.append(swing.price)
            self._swing_indices.append(swing.bar_index)
            self._swing_ts.append(swing.ts)
            if len(self._swing_prices) > self._max_swings:
                self._swing_prices.pop(0)
                self._swing_indices.pop(0)
                self._swing_ts.pop(0)

        self._bar_index += 1

        if len(self._swing_prices) >= 1:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        if not self._swing_prices:
            self._levels = []
            return

        clusters = agglomerative_cluster(
            self._swing_prices, self._cluster_distance
        )

        # Build sorted mapping from prices to (index, ts) for reconstruction
        sorted_entries = sorted(
            zip(self._swing_prices, self._swing_indices, self._swing_ts),
            key=lambda x: x[0],
        )

        max_bounces = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        entry_idx = 0
        for members, centroid in clusters:
            member_indices: list[int] = []
            member_ts: list[int] = []
            for _ in members:
                if entry_idx < len(sorted_entries):
                    member_indices.append(sorted_entries[entry_idx][1])
                    member_ts.append(sorted_entries[entry_idx][2])
                    entry_idx += 1

            bounce_count = len(members)
            strength = bounce_count / max_bounces if max_bounces > 0 else 0.0

            levels.append(
                KeyLevel(
                    price=centroid,
                    strength=min(1.0, strength),
                    bounce_count=bounce_count,
                    first_seen_ts=min(member_ts) if member_ts else 0,
                    last_touched_ts=max(member_ts) if member_ts else 0,
                    zone_upper=max(members),
                    zone_lower=min(members),
                    source="swing_cluster",
                    meta=SwingClusterMeta(
                        cluster_radius=self._cluster_distance,
                        pivot_indices=tuple(member_indices),
                    ),
                )
            )

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
