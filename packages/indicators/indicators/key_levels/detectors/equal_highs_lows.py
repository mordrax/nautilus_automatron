"""EqualHighsLowsDetector — detect levels where multiple swing highs or lows
touch approximately the same price, tracked over their full lifecycle.

Each level is born when at least `min_touches` swings on the same side cluster
within tolerance, lives while bars revisit / bounce off it, and ends either by
breaking (close beyond level by `break_atr_multiple` x ATR for
`break_consecutive_bars` consecutive bars) or by aging out (no touch for
`max_idle_bars` bars).

Strength is computed on demand in `levels()` as
    exp(-(bounce_count - min_touches) / strength_decay_k)
so that 2 swings -> 1.0, 5 swings -> ~0.37, 10 swings -> ~0.05.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import EqualHighsLowsMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


@dataclass
class _TrackedLevel:
    """Internal mutable state for one level being tracked over time."""

    id: int
    side: Literal["high", "low"]
    centroid: float
    members: list[float]
    member_ts: list[int]
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int = 0


class EqualHighsLowsDetector:

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
        self._pending_swings: dict[Literal["high", "low"], list[tuple[float, int]]] = {
            "high": [],
            "low": [],
        }
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "equal_highs_lows"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._period + 1

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        # Track bar interval (used for aged-out check). Detected from the gap
        # between the first two bars; falls back to a sensible default later.
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

        # Always buffer swings — even before ATR is ready — so the very first
        # cluster can form as soon as tolerance is computable.
        if swing is not None:
            self._pending_swings[swing.side].append((swing.price, swing.ts))

        if not self._atr.ready:
            return

        tolerance = self._atr.value * self._tolerance_atr_multiple

        # Update active levels: bar-level touches, breaks, aged-out.
        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # Try to attach the most recent buffered swing (if any) to an active
        # level on the same side; otherwise it stays buffered until promoted.
        if swing is not None:
            self._attach_or_keep(swing.price, swing.ts, swing.side, tolerance)

        # Promote any buffered cluster that now meets min_touches on either
        # side — both sides are tested every bar so backlog clears as soon
        # as ATR is ready.
        for side in ("high", "low"):
            self._try_promote_pending(side, tolerance)  # type: ignore[arg-type]

    def _apply_bar_to_level(
        self,
        lvl: _TrackedLevel,
        high: float,
        low: float,
        close: float,
        ts: int,
        tolerance: float,
    ) -> None:
        # Bar-level touch: bar's high/low range overlaps the tolerance band
        # around the centroid.
        band_upper = lvl.centroid + tolerance
        band_lower = lvl.centroid - tolerance
        if low <= band_upper and high >= band_lower:
            lvl.touch_count += 1
            lvl.last_touch_ts = ts

        # Break check: a close strongly beyond the level for K consecutive bars.
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

        # Aged-out check: no touch for too long. Use detected bar interval, or
        # fall back to a 1-bar approximation when we haven't seen two bars yet.
        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - lvl.last_touch_ts > idle_ns:
            lvl.end_ts = lvl.last_touch_ts

    def _attach_or_keep(
        self,
        price: float,
        ts: int,
        side: Literal["high", "low"],
        tolerance: float,
    ) -> None:
        """If the just-confirmed swing matches an active level, fold it in
        and drop it from the pending buffer. Otherwise leave it buffered for
        later promotion via `_try_promote_pending`.
        """
        for lvl in self._tracked:
            if lvl.end_ts is not None or lvl.side != side:
                continue
            if abs(price - lvl.centroid) <= tolerance:
                lvl.members.append(price)
                lvl.member_ts.append(ts)
                lvl.centroid = sum(lvl.members) / len(lvl.members)
                lvl.bounce_count += 1
                lvl.last_touch_ts = ts
                # Remove the matching swing from the pending buffer (it was
                # just appended in `update`, so it's at the tail).
                buf = self._pending_swings[side]
                if buf and buf[-1] == (price, ts):
                    buf.pop()
                return

    def _try_promote_pending(
        self, side: Literal["high", "low"], tolerance: float,
    ) -> None:
        """Find a contiguous-by-time subset of buffered swings whose mutual
        price range is within tolerance and size >= min_touches. Promote them
        to a new tracked level. Promoted swings are removed from the buffer.
        """
        buf = self._pending_swings[side]
        if len(buf) < self._min_touches:
            return

        # Greedy scan: try every starting index; collect a maximal subsequent
        # window of swings whose collective spread stays <= tolerance.
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
                if best is None or len(members) > len(best):
                    best = members
                    # Earliest qualifying window — break, the spec says a new
                    # cluster forms as soon as min_touches mutually close
                    # swings exist.
                    break

        if best is None:
            return

        prices = [buf[k][0] for k in best]
        timestamps = [buf[k][1] for k in best]
        centroid = sum(prices) / len(prices)
        start_ts = max(timestamps)  # ts of most recent swing in the subset
        last_touch_ts = start_ts

        self._tracked.append(_TrackedLevel(
            id=self._next_id,
            side=side,
            centroid=centroid,
            members=prices,
            member_ts=timestamps,
            start_ts=start_ts,
            end_ts=None,
            bounce_count=len(prices),
            touch_count=0,
            last_touch_ts=last_touch_ts,
            bars_through=0,
        ))
        self._next_id += 1

        # Remove promoted swings from the buffer (high indices first).
        for idx in sorted(best, reverse=True):
            buf.pop(idx)

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            strength = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            # Clamp into [0, 1] — exp can overshoot 1 if bounce_count drops
            # below min_touches via some future change; defensive.
            strength = max(0.0, min(1.0, strength))

            zone_upper = max(lvl.members) if lvl.members else lvl.centroid
            zone_lower = min(lvl.members) if lvl.members else lvl.centroid

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="equal_highs_lows",
                bounce_count=lvl.bounce_count,
                zone_upper=zone_upper,
                zone_lower=zone_lower,
                meta=EqualHighsLowsMeta(
                    touch_prices=tuple(lvl.members),
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
        self._pending_swings = {"high": [], "low": []}
        self._next_id = 0
