"""MarketProfileDetector — Time-Price Opportunity (TPO) profile
(lifecycle-tracked).

Bins price into ``bin_count`` cells per session and counts how many TPO
periods (``slice_minutes``-wide time slices) had price visit each cell.
At session end, computes:

- POC (Point of Control): the cell with the highest TPO count.
- VAH / VAL (Value Area High/Low): the upper/lower edges of the band that
  captures ``value_area_pct`` of total TPOs starting at the POC and
  expanding outward.

Each day produces 3 levels (POC, VAH, VAL), born at the day boundary and
finalized when the next day's set emits, when the level is broken by
sustained close beyond it, or when no touch occurs for ``max_idle_bars``.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, MarketProfileMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


@dataclass
class _SessionProfile:
    session_high: float = float("-inf")
    session_low: float = float("inf")
    tpo_counts: dict[int, int] = field(default_factory=dict)
    last_slice_key: int | None = None
    total_tpo_periods: int = 0
    session_date: datetime.date | None = None
    has_data: bool = False


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    role: Literal["poc", "vah", "val"]
    centroid: float
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    tpo_count: int
    total_tpo_periods: int


def _bin_index(price: float, base: float, bin_size: float) -> int:
    if bin_size <= 0:
        return 0
    return int((price - base) / bin_size)


class MarketProfileDetector:

    def __init__(
        self,
        slice_minutes: int = 30,
        bin_count: int = 50,
        value_area_pct: float = 0.7,
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        max_idle_bars: int = 1000,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._slice_minutes = slice_minutes
        self._bin_count = bin_count
        self._value_area_pct = value_area_pct
        self._break_atr_multiple = break_atr_multiple
        self._break_consecutive_bars = break_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._strength_decay_k = strength_decay_k
        self._min_touches = min_touches

        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)
        self._bar_index: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

        self._current_profile = _SessionProfile()
        self._current_session_date: datetime.date | None = None

        self._tracked: list[_TrackedLevel] = []
        self._active_ids: list[int] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "market_profile_tpo"

    @property
    def warmup_bars(self) -> int:
        return 1

    def _slice_key(self, dt: datetime.datetime) -> int:
        minutes_since_midnight = dt.hour * 60 + dt.minute
        return minutes_since_midnight // self._slice_minutes

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

        if self._atr.ready:
            tolerance = 0.25 * self._atr.value
            for idx in self._active_ids:
                lvl = self._tracked[idx]
                if lvl.end_ts is None:
                    self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)
            if swing is not None:
                for idx in self._active_ids:
                    lvl = self._tracked[idx]
                    if lvl.end_ts is not None or lvl.side != swing.side:
                        continue
                    if abs(swing.price - lvl.centroid) <= tolerance:
                        lvl.bounce_count += 1
                        lvl.last_touch_ts = swing.ts

        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        bar_date = dt.date()

        # Detect new session — finalize previous and emit its levels.
        if (
            self._current_session_date is not None
            and bar_date != self._current_session_date
        ):
            if self._current_profile.has_data:
                self._finalize_and_emit(close, ts)
            self._current_profile = _SessionProfile()

        self._current_session_date = bar_date

        profile = self._current_profile

        if not profile.has_data:
            profile.session_high = high
            profile.session_low = low
            profile.session_date = bar_date
            profile.has_data = True
        else:
            profile.session_high = max(profile.session_high, high)
            profile.session_low = min(profile.session_low, low)

        slice_key = self._slice_key(dt)
        if slice_key != profile.last_slice_key:
            profile.total_tpo_periods += 1
            profile.last_slice_key = slice_key

        session_range = profile.session_high - profile.session_low
        if session_range <= 0:
            return

        bin_size = session_range / self._bin_count
        low_bin = max(0, _bin_index(low, profile.session_low, bin_size))
        high_bin = min(
            self._bin_count - 1, _bin_index(high, profile.session_low, bin_size),
        )
        for b in range(low_bin, high_bin + 1):
            profile.tpo_counts[b] = profile.tpo_counts.get(b, 0) + 1

    def _finalize_and_emit(self, close: float, ts: int) -> None:
        # Finalize active levels.
        for idx in self._active_ids:
            lvl = self._tracked[idx]
            if lvl.end_ts is None:
                lvl.end_ts = ts

        new_active = self._compute_levels(close, ts)
        self._active_ids = new_active

    def _compute_levels(self, close: float, ts: int) -> list[int]:
        profile = self._current_profile
        if not profile.has_data or not profile.tpo_counts:
            return []

        session_range = profile.session_high - profile.session_low
        if session_range <= 0:
            return []

        bin_size = session_range / self._bin_count

        # POC.
        poc_bin = max(profile.tpo_counts, key=lambda b: profile.tpo_counts[b])
        poc_price = profile.session_low + (poc_bin + 0.5) * bin_size
        poc_count = profile.tpo_counts[poc_bin]

        # Value Area: expand outward from POC.
        total_tpo = sum(profile.tpo_counts.values())
        target_tpo = total_tpo * self._value_area_pct

        va_bins = {poc_bin}
        accumulated = profile.tpo_counts[poc_bin]
        lower_edge = poc_bin - 1
        upper_edge = poc_bin + 1

        while accumulated < target_tpo:
            lower_count = (
                profile.tpo_counts.get(lower_edge, 0) if lower_edge >= 0 else 0
            )
            upper_count = (
                profile.tpo_counts.get(upper_edge, 0)
                if upper_edge < self._bin_count
                else 0
            )
            if lower_count == 0 and upper_count == 0:
                break
            if lower_count >= upper_count:
                va_bins.add(lower_edge)
                accumulated += lower_count
                lower_edge -= 1
            else:
                va_bins.add(upper_edge)
                accumulated += upper_count
                upper_edge += 1

        va_low_bin = min(va_bins)
        va_high_bin = max(va_bins)
        va_low_price = profile.session_low + va_low_bin * bin_size
        va_high_price = profile.session_low + (va_high_bin + 1) * bin_size
        va_tpo = sum(profile.tpo_counts.get(b, 0) for b in va_bins)

        new_active: list[int] = []
        for role, price, tpo_count in (
            ("poc", poc_price, poc_count),
            ("vah", va_high_price, va_tpo),
            ("val", va_low_price, va_tpo),
        ):
            side: Literal["high", "low"] = "high" if price >= close else "low"
            idx = len(self._tracked)
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=side,
                role=role,  # type: ignore[arg-type]
                centroid=price,
                start_ts=ts,
                end_ts=None,
                bounce_count=1,
                touch_count=0,
                last_touch_ts=ts,
                bars_through=0,
                tpo_count=tpo_count,
                total_tpo_periods=profile.total_tpo_periods,
            ))
            self._next_id += 1
            new_active.append(idx)
        return new_active

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

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for lvl in self._tracked:
            decay = math.exp(
                -(lvl.bounce_count - self._min_touches) / self._strength_decay_k
            )
            decay = max(0.0, min(1.0, decay))
            base = 0.9 if lvl.role == "poc" else 0.7
            strength = max(0.0, min(1.0, base * decay))

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="market_profile_tpo",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid,
                zone_lower=lvl.centroid,
                meta=MarketProfileMeta(
                    tpo_count=lvl.tpo_count,
                    role=lvl.role,
                    total_tpo_periods=lvl.total_tpo_periods,
                    side=lvl.side,
                    touch_count=lvl.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._swing_detector.reset()
        self._bar_index = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._current_profile = _SessionProfile()
        self._current_session_date = None
        self._tracked.clear()
        self._active_ids.clear()
        self._next_id = 0
