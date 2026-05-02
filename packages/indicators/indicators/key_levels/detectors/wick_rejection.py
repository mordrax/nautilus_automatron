"""WickRejectionDetector — detect levels where multiple long-wick rejections
cluster, tracked over their full lifecycle.

A long wick indicates price rejection at a level. Multiple rejections in the
same price zone form a key level. Each level is born when at least
`min_rejections` rejections on the same side cluster within tolerance, lives
while bars revisit / bounce off it, and ends either by breaking (close beyond
level by `break_atr_multiple` x ATR for `break_consecutive_bars` consecutive
bars) or by aging out (no touch for `max_idle_bars` bars).

Strength is computed on demand in `levels()` as
    exp(-(bounce_count - min_rejections) / strength_decay_k)
so that 2 rejections -> 1.0, 5 rejections -> ~0.37, 10 rejections -> ~0.05.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, WickRejectionMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedLevel:
    """Internal mutable state for one rejection-cluster level being tracked."""

    id: int
    side: Literal["high", "low"]
    centroid: float
    members: list[float]            # rejection prices
    member_ts: list[int]
    member_ratios: list[float]
    start_ts: int
    end_ts: int | None
    bounce_count: int               # number of rejections folded in
    touch_count: int                # bar-level touches (independent of bounces)
    last_touch_ts: int
    bars_through: int = 0


class WickRejectionDetector:

    def __init__(
        self,
        min_wick_ratio: float = 2.0,
        zone_atr_multiple: float = 1.0,
        atr_period: int = 14,
        min_rejections: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        strength_decay_k: float = 3.0,
    ) -> None:
        self._min_wick_ratio = min_wick_ratio
        self._zone_atr_multiple = zone_atr_multiple
        self._atr_period = atr_period
        self._min_rejections = min_rejections
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k

        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._tracked: list[_TrackedLevel] = []
        # Pending rejection events buffered until a cluster of size
        # >= min_rejections forms within tolerance.
        self._pending_rejections: dict[
            Literal["high", "low"], list[tuple[float, float, int]]
        ] = {"high": [], "low": []}
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "wick_rejection"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        open_ = float(bar.open)
        close = float(bar.close)
        ts = bar.ts_event

        # Track bar interval for the aged-out check.
        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)
        self._bar_index += 1

        if not self._atr.ready:
            return

        atr_value = self._atr.value
        tolerance = atr_value * self._zone_atr_multiple

        # 1) Update active levels: bar-level touches, breaks, aged-out.
        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # 2) Detect rejection events on this bar.
        rejections = self._detect_rejections(open_, high, low, close, atr_value)

        # 3) Try to attach each rejection to an active level on the matching
        # side; otherwise buffer it for later promotion.
        for side, price, ratio in rejections:
            attached = self._attach_or_keep(price, ratio, ts, side, tolerance)
            if not attached:
                self._pending_rejections[side].append((price, ratio, ts))

        # 4) Try to promote buffered clusters on every bar (both sides).
        for side in ("high", "low"):
            self._try_promote_pending(side, tolerance)  # type: ignore[arg-type]

    # ------------------------------------------------------------ rejection detection

    def _detect_rejections(
        self,
        open_: float,
        high: float,
        low: float,
        close: float,
        atr_value: float,
    ) -> list[tuple[Literal["high", "low"], float, float]]:
        """Return rejection events on this bar.

        Each event is (side, price, ratio):
            - "low"  → lower-wick rejection (price = bar low)  → support
            - "high" → upper-wick rejection (price = bar high) → resistance

        Doji handling: when the body is tiny (<= min_body), a single wick
        longer than half the ATR also counts as a rejection.
        """
        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low

        # Use a small fraction of ATR as the doji body threshold so the
        # detector behaves consistently across instruments.
        min_body = 0.1 * atr_value
        doji_wick_threshold = 0.5 * atr_value

        out: list[tuple[Literal["high", "low"], float, float]] = []

        if body > min_body:
            if lower_wick > 0 and lower_wick / body >= self._min_wick_ratio:
                out.append(("low", low, lower_wick / body))
            if upper_wick > 0 and upper_wick / body >= self._min_wick_ratio:
                out.append(("high", high, upper_wick / body))
        else:
            # Doji: pick the longer wick as the rejection direction (or both
            # if both exceed the threshold).
            if lower_wick > doji_wick_threshold:
                ratio = lower_wick / max(body, min_body)
                out.append(("low", low, ratio))
            if upper_wick > doji_wick_threshold:
                ratio = upper_wick / max(body, min_body)
                out.append(("high", high, ratio))

        return out

    # ------------------------------------------------------------ lifecycle helpers

    def _apply_bar_to_level(
        self,
        lvl: _TrackedLevel,
        high: float,
        low: float,
        close: float,
        ts: int,
        tolerance: float,
    ) -> None:
        # Break check first so the breaking bar doesn't inflate touch_count.
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

        # Bar-level touch: bar range overlaps tolerance band around centroid.
        band_upper = lvl.centroid + tolerance
        band_lower = lvl.centroid - tolerance
        if low <= band_upper and high >= band_lower:
            lvl.touch_count += 1
            lvl.last_touch_ts = ts

        # Aged-out check.
        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - lvl.last_touch_ts > idle_ns:
            lvl.end_ts = lvl.last_touch_ts

    def _attach_or_keep(
        self,
        price: float,
        ratio: float,
        ts: int,
        side: Literal["high", "low"],
        tolerance: float,
    ) -> bool:
        """If the rejection matches an active same-side level, fold it in and
        return True. Otherwise return False so the caller can buffer it.
        """
        best: _TrackedLevel | None = None
        best_dist = tolerance
        for lvl in self._tracked:
            if lvl.end_ts is not None or lvl.side != side:
                continue
            dist = abs(price - lvl.centroid)
            if dist <= best_dist:
                best = lvl
                best_dist = dist

        if best is None:
            return False

        best.members.append(price)
        best.member_ts.append(ts)
        best.member_ratios.append(ratio)
        best.centroid = sum(best.members) / len(best.members)
        best.bounce_count += 1
        best.last_touch_ts = ts
        return True

    def _try_promote_pending(
        self,
        side: Literal["high", "low"],
        tolerance: float,
    ) -> None:
        """Find a contiguous-by-time subset of buffered rejections whose
        mutual price range is within tolerance and size >= min_rejections.
        Promote them to a new tracked level.
        """
        buf = self._pending_rejections[side]
        if len(buf) < self._min_rejections:
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
            if len(members) >= self._min_rejections:
                if best is None or len(members) > len(best):
                    best = members
                    break

        if best is None:
            return

        prices = [buf[k][0] for k in best]
        ratios = [buf[k][1] for k in best]
        timestamps = [buf[k][2] for k in best]
        centroid = sum(prices) / len(prices)
        start_ts = max(timestamps)
        last_touch_ts = start_ts

        self._tracked.append(_TrackedLevel(
            id=self._next_id,
            side=side,
            centroid=centroid,
            members=prices,
            member_ts=timestamps,
            member_ratios=ratios,
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
                -(lvl.bounce_count - self._min_rejections) / self._strength_decay_k
            )
            strength = max(0.0, min(1.0, strength))

            zone_upper = max(lvl.members) if lvl.members else lvl.centroid
            zone_lower = min(lvl.members) if lvl.members else lvl.centroid
            avg_ratio = (
                sum(lvl.member_ratios) / len(lvl.member_ratios)
                if lvl.member_ratios else 0.0
            )

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="wick_rejection",
                bounce_count=lvl.bounce_count,
                zone_upper=zone_upper,
                zone_lower=zone_lower,
                meta=WickRejectionMeta(
                    rejection_count=lvl.bounce_count,
                    avg_wick_ratio=avg_ratio,
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._tracked.clear()
        self._pending_rejections = {"high": [], "low": []}
        self._next_id = 0
