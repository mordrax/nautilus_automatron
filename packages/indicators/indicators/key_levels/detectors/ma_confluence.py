"""MaConfluenceDetector — lifecycle-tracked level emitted when N+ EMAs cluster.

The cluster price moves over time, so this detector follows the
``atr_volatility`` band-replacement pattern: when the *current* cluster centroid
drifts beyond ``replacement_atr * ATR`` from the previously-emitted level price
(or when MAs separate so confluence is lost), the existing level is finalized
and a fresh one is emitted at the new centroid.

Lifecycle:
- **Start**: when ``min_converging`` MAs first sit within
  ``spread_threshold * ATR`` of each other.
- **End**: a sustained close ``break_atr_multiple * ATR`` beyond the centroid
  for ``break_consecutive_bars`` bars; or aged-out (``max_idle_bars`` with no
  touch); or replaced when the running centroid drifts beyond
  ``confluence_break_atr * ATR`` (treated as the level moving on).

`bounce_count` is the number of EMAs participating; `touch_count` increments
on bar-level overlaps with the cluster band. `side` is "high" if the cluster
is currently above price, "low" otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, MaConfluenceMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    centroid: float
    members: tuple[float, ...]
    member_periods: tuple[int, ...]
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    spread: float


class MaConfluenceDetector:

    def __init__(
        self,
        ma_periods: tuple[int, ...] = (9, 21, 50, 100, 200),
        min_converging: int = 3,
        spread_threshold: float = 0.5,
        atr_period: int = 14,
        confluence_break_atr: float = 1.0,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
    ) -> None:
        self._ma_periods = ma_periods
        self._min_converging = min_converging
        self._spread_threshold = spread_threshold
        self._confluence_break_atr = confluence_break_atr
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars

        self._atr = StreamingAtr(period=atr_period)
        self._alphas = tuple(2.0 / (p + 1) for p in ma_periods)
        self._ema_values: list[float | None] = [None] * len(ma_periods)
        self._bar_count = 0

        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0
        self._active_id: int | None = None

    @property
    def name(self) -> str:
        return "ma_confluence"

    @property
    def warmup_bars(self) -> int:
        return max(self._ma_periods)

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
        self._bar_count += 1

        # Update EMAs.
        for i, period in enumerate(self._ma_periods):
            if self._ema_values[i] is None:
                if self._bar_count >= period:
                    self._ema_values[i] = close
            else:
                a = self._alphas[i]
                self._ema_values[i] = close * a + self._ema_values[i] * (1 - a)

        if not self._atr.ready or any(v is None for v in self._ema_values):
            return

        atr_value = self._atr.value
        tolerance = 0.25 * atr_value

        # 1) Lifecycle update on existing levels.
        for lvl in self._tracked:
            if lvl.end_ts is not None:
                continue
            self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)

        # 2) Compute current confluence (if any) and emit / replace.
        cluster = self._find_confluence(close)
        active = (
            self._tracked[self._active_id]
            if self._active_id is not None
            and self._tracked[self._active_id].end_ts is None
            else None
        )

        if cluster is None:
            # No confluence — finalize active level, if any.
            if active is not None:
                active.end_ts = ts
                self._active_id = None
            return

        new_centroid, new_members, new_periods, new_side = cluster

        if active is None:
            self._emit(
                centroid=new_centroid,
                members=new_members,
                periods=new_periods,
                side=new_side,
                ts=ts,
            )
            return

        drift = abs(new_centroid - active.centroid)
        if drift > self._confluence_break_atr * atr_value:
            # Level has moved on — finalize and emit fresh.
            active.end_ts = ts
            self._active_id = None
            self._emit(
                centroid=new_centroid,
                members=new_members,
                periods=new_periods,
                side=new_side,
                ts=ts,
            )
            return

        # Same level continues — refresh members for accurate meta. `side` is
        # held stable from emit time so break semantics don't flip when price
        # walks across the cluster (a level born as resistance stays a
        # resistance level until finalized).
        active.centroid = new_centroid
        active.members = new_members
        active.member_periods = new_periods
        active.spread = max(new_members) - min(new_members)
        active.bounce_count = max(active.bounce_count, len(new_members))

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
            if self._active_id == lvl.id:
                self._active_id = None
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
            if self._active_id == lvl.id:
                self._active_id = None

    def _find_confluence(
        self,
        price: float,
    ) -> tuple[float, tuple[float, ...], tuple[int, ...], Literal["high", "low"]] | None:
        atr_value = self._atr.value
        if atr_value <= 0:
            return None

        ema_values = [v for v in self._ema_values if v is not None]
        max_spread = self._spread_threshold * atr_value

        # Indexed sort so we keep periods alongside values.
        indexed = sorted(
            zip(ema_values, self._ma_periods),
            key=lambda x: x[0],
        )
        sorted_vals = [v for v, _ in indexed]
        sorted_periods = [p for _, p in indexed]

        # Largest contiguous subset whose spread < max_spread.
        best_start = 0
        best_len = 0
        n = len(sorted_vals)
        for start in range(n):
            for end in range(start + self._min_converging, n + 1):
                spread = sorted_vals[end - 1] - sorted_vals[start]
                if spread < max_spread:
                    if end - start > best_len:
                        best_start = start
                        best_len = end - start
                else:
                    break

        if best_len < self._min_converging:
            return None

        members = tuple(sorted_vals[best_start : best_start + best_len])
        periods = tuple(sorted(sorted_periods[best_start : best_start + best_len]))
        centroid = sum(members) / len(members)
        side: Literal["high", "low"] = "high" if centroid >= price else "low"
        return centroid, members, periods, side

    def _emit(
        self,
        centroid: float,
        members: tuple[float, ...],
        periods: tuple[int, ...],
        side: Literal["high", "low"],
        ts: int,
    ) -> None:
        spread = max(members) - min(members) if members else 0.0
        lvl = _TrackedLevel(
            id=self._next_id,
            side=side,
            centroid=centroid,
            members=members,
            member_periods=periods,
            start_ts=ts,
            end_ts=None,
            bounce_count=len(members),
            touch_count=0,
            last_touch_ts=ts,
            bars_through=0,
            spread=spread,
        )
        self._tracked.append(lvl)
        self._active_id = lvl.id
        self._next_id += 1

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            # Strength: confluence ratio * tightness — clamped to [0, 1].
            confluence_ratio = lvl.bounce_count / max(1, len(self._ma_periods))
            atr_value = self._atr.value if self._atr.ready else 1.0
            tightness = (
                1.0 / (1.0 + (lvl.spread / atr_value if atr_value > 0 else 0.0))
            )
            strength = max(0.0, min(1.0, confluence_ratio * tightness))

            zone_upper = max(lvl.members) if lvl.members else lvl.centroid
            zone_lower = min(lvl.members) if lvl.members else lvl.centroid
            spread_percent = (
                lvl.spread / lvl.centroid * 100.0 if lvl.centroid > 0 else 0.0
            )

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="ma_confluence",
                bounce_count=lvl.bounce_count,
                zone_upper=zone_upper,
                zone_lower=zone_lower,
                meta=MaConfluenceMeta(
                    ma_count=len(lvl.member_periods),
                    ma_periods=lvl.member_periods,
                    spread_percent=spread_percent,
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._ema_values = [None] * len(self._ma_periods)
        self._bar_count = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._tracked.clear()
        self._next_id = 0
        self._active_id = None
