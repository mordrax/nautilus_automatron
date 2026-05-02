"""SwingClusterDetector — detect levels from clustered swing highs and lows
(both sides), tracked over their full lifecycle.

Differs from EqualHighsLowsDetector by mixing both swing-high and swing-low
pivots into the same clustering pool — a level can absorb either side as long
as the price falls within tolerance. Each level's `side` is determined by the
predominant swing direction in its membership ("high" if more high swings,
"low" otherwise; ties resolve to "high").

Lifecycle is the same shape as equal_highs_lows: born when at least
`min_touches` swings cluster within tolerance; updated per-bar with break /
aged-out / touch checks; ended when the close strongly breaks the level for
``break_consecutive_bars`` consecutive bars or no touch occurs for
``max_idle_bars``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, SwingClusterMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


@dataclass
class _TrackedLevel:
    id: int
    centroid: float
    members: list[float]
    member_ts: list[int]
    member_indices: list[int]
    member_sides: list[Literal["high", "low"]]
    side: Literal["high", "low"]
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int = 0


class SwingClusterDetector:

    def __init__(
        self,
        period: int = 2,
        tolerance_atr_multiple: float = 0.5,
        atr_period: int = 14,
        min_touches: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
    ) -> None:
        self._period = period
        self._tolerance_atr_multiple = tolerance_atr_multiple
        self._atr_period = atr_period
        self._min_touches = min_touches
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k

        self._swing_detector = SwingDetector(period=period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._tracked: list[_TrackedLevel] = []
        # Single buffer regardless of swing side — clusters mix both.
        self._pending: list[
            tuple[float, int, int, Literal["high", "low"]]
        ] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._period + 1

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        self._bar_index += 1

        if swing is not None:
            self._pending.append(
                (swing.price, swing.ts, swing.bar_index, swing.side)
            )

        if not self._atr.ready:
            return

        tolerance = self._atr.value * self._tolerance_atr_multiple

        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        if swing is not None:
            self._attach_or_keep(
                swing.price, swing.ts, swing.bar_index, swing.side, tolerance,
            )

        self._try_promote_pending(tolerance)

    def _apply_bar_to_level(
        self,
        lvl: _TrackedLevel,
        high: float,
        low: float,
        close: float,
        ts: int,
        tolerance: float,
    ) -> None:
        atr_value = self._atr.value
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

    def _attach_or_keep(
        self,
        price: float,
        ts: int,
        bar_index: int,
        side: Literal["high", "low"],
        tolerance: float,
    ) -> None:
        """Attach a swing (either side) to the closest active level whose
        centroid is within tolerance. Both sides share the same level pool —
        a high swing can fold into a level that started life as a low cluster
        and vice versa. Update side based on majority membership.
        """
        best: _TrackedLevel | None = None
        best_dist = tolerance
        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            dist = abs(price - lvl.centroid)
            if dist <= best_dist:
                best = lvl
                best_dist = dist

        if best is None:
            return

        best.members.append(price)
        best.member_ts.append(ts)
        best.member_indices.append(bar_index)
        best.member_sides.append(side)
        best.centroid = sum(best.members) / len(best.members)
        best.bounce_count += 1
        best.last_touch_ts = ts
        # Recompute side from majority — ties → "high".
        highs = sum(1 for s in best.member_sides if s == "high")
        lows = len(best.member_sides) - highs
        best.side = "high" if highs >= lows else "low"

        # Remove from buffer (just-appended).
        if self._pending and self._pending[-1][0] == price and self._pending[-1][1] == ts:
            self._pending.pop()

    def _try_promote_pending(self, tolerance: float) -> None:
        """Find a contiguous-by-time subset of buffered swings (mixed sides)
        whose mutual price range is within tolerance and size >= min_touches.
        Promote them to a new tracked level.
        """
        buf = self._pending
        if len(buf) < self._min_touches:
            return

        n = len(buf)
        best: list[int] | None = None
        for i in range(n):
            members: list[int] = [i]
            lo = buf[i][0]
            hi = buf[i][0]
            for j in range(i + 1, n):
                p = buf[j][0]
                new_lo = min(lo, p)
                new_hi = max(hi, p)
                if new_hi - new_lo <= tolerance:
                    members.append(j)
                    lo = new_lo
                    hi = new_hi
            if len(members) >= self._min_touches:
                best = members
                break

        if best is None:
            return

        prices = [buf[k][0] for k in best]
        timestamps = [buf[k][1] for k in best]
        bar_indices = [buf[k][2] for k in best]
        sides_lit = [buf[k][3] for k in best]
        centroid = sum(prices) / len(prices)
        start_ts = max(timestamps)
        last_touch_ts = start_ts
        highs = sum(1 for s in sides_lit if s == "high")
        lows = len(sides_lit) - highs
        side: Literal["high", "low"] = "high" if highs >= lows else "low"

        self._tracked.append(_TrackedLevel(
            id=self._next_id,
            centroid=centroid,
            members=prices,
            member_ts=timestamps,
            member_indices=bar_indices,
            member_sides=sides_lit,
            side=side,
            start_ts=start_ts,
            end_ts=None,
            bounce_count=len(prices),
            touch_count=0,
            last_touch_ts=last_touch_ts,
            bars_through=0,
        ))
        self._next_id += 1

        for idx in sorted(best, reverse=True):
            buf.pop(idx)

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            strength = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            strength = max(0.0, min(1.0, strength))

            zone_upper = max(lvl.members) if lvl.members else lvl.centroid
            zone_lower = min(lvl.members) if lvl.members else lvl.centroid

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="swing_cluster",
                bounce_count=lvl.bounce_count,
                zone_upper=zone_upper,
                zone_lower=zone_lower,
                meta=SwingClusterMeta(
                    cluster_radius=zone_upper - zone_lower,
                    pivot_indices=tuple(lvl.member_indices),
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._tracked.clear()
        self._pending.clear()
        self._next_id = 0
