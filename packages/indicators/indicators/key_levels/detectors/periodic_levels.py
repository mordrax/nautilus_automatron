"""PeriodicLevelDetector — previous period H/L/C as key levels.

Tracks running H/L/C for daily, weekly, and/or monthly periods.
When a period boundary is crossed, the completed period's stats become levels.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PeriodicLevelMeta

PeriodType = Literal["daily", "weekly", "monthly"]


@dataclass
class _PeriodTracker:
    """Mutable running state for a single period type."""

    high: float = float("-inf")
    low: float = float("inf")
    close: float = 0.0
    period_start: datetime.date | None = None
    has_data: bool = False


def _period_key(dt: datetime.datetime, period: PeriodType) -> object:
    """Return a hashable key that changes when a new period starts."""
    d = dt.date()
    if period == "daily":
        return d
    if period == "weekly":
        # ISO calendar: (year, week_number)
        iso = d.isocalendar()
        return (iso[0], iso[1])
    # monthly
    return (d.year, d.month)


class PeriodicLevelDetector:

    def __init__(
        self,
        periods: tuple[PeriodType, ...] = ("daily",),
        exchange_timezone: str = "UTC",
    ) -> None:
        self._periods = periods
        self._exchange_timezone = exchange_timezone

        self._trackers: dict[PeriodType, _PeriodTracker] = {
            p: _PeriodTracker() for p in periods
        }
        self._prev_keys: dict[PeriodType, object] = {p: None for p in periods}

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "periodic_level"

    @property
    def warmup_bars(self) -> int:
        return 1

    def update(self, bar: Bar) -> None:
        ts = bar.ts_event
        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)

        for period in self._periods:
            key = _period_key(dt, period)
            tracker = self._trackers[period]

            if self._prev_keys[period] is not None and key != self._prev_keys[period]:
                # Period rolled over — emit levels from completed period
                if tracker.has_data:
                    self._emit_levels(period, tracker, ts)
                # Reset tracker for new period
                tracker.high = high
                tracker.low = low
                tracker.close = close
                tracker.period_start = dt.date()
                tracker.has_data = True
            else:
                # Same period — update running stats
                if not tracker.has_data:
                    tracker.high = high
                    tracker.low = low
                    tracker.period_start = dt.date()
                    tracker.has_data = True
                else:
                    tracker.high = max(tracker.high, high)
                    tracker.low = min(tracker.low, low)
                tracker.close = close

            self._prev_keys[period] = key

    def _emit_levels(
        self, period: PeriodType, tracker: _PeriodTracker, ts: int
    ) -> None:
        period_start = tracker.period_start or datetime.date(2000, 1, 1)

        # Remove previous levels for this period type
        self._levels = [
            lv
            for lv in self._levels
            if not (
                isinstance(lv.meta, PeriodicLevelMeta)
                and lv.meta.period == period
            )
        ]

        strength_map = {"high": 0.8, "low": 0.8, "close": 0.6}
        price_map = {"high": tracker.high, "low": tracker.low, "close": tracker.close}

        for level_type in ("high", "low", "close"):
            self._levels.append(
                KeyLevel(
                    price=price_map[level_type],
                    strength=strength_map[level_type],
                    bounce_count=1,
                    first_seen_ts=ts,
                    last_touched_ts=ts,
                    zone_upper=price_map[level_type],
                    zone_lower=price_map[level_type],
                    source="periodic_level",
                    meta=PeriodicLevelMeta(
                        period=period,
                        level_type=level_type,
                        period_start=period_start,
                    ),
                )
            )

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._trackers = {p: _PeriodTracker() for p in self._periods}
        self._prev_keys = {p: None for p in self._periods}
        self._levels = []
