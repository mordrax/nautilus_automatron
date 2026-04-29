"""OpeningRangeDetector — track high and low of the first N minutes after open.

Once the opening range period elapses, the high and low are locked as key
levels for the rest of the session. A new day resets the range.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, OpeningRangeMeta


@dataclass
class _RangeState:
    """Mutable state for the current day's opening range."""

    high: float = float("-inf")
    low: float = float("inf")
    range_start_ts: int = 0
    locked: bool = False
    current_date: datetime.date | None = None
    has_data: bool = False


class OpeningRangeDetector:

    def __init__(
        self,
        range_minutes: int = 30,
        market_open_hour_utc: int = 9,
        exchange_timezone: str = "UTC",
    ) -> None:
        self._range_minutes = range_minutes
        self._market_open_hour_utc = market_open_hour_utc
        self._exchange_timezone = exchange_timezone

        self._state = _RangeState()
        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "opening_range"

    @property
    def warmup_bars(self) -> int:
        return 1

    def update(self, bar: Bar) -> None:
        ts = bar.ts_event
        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        bar_date = dt.date()
        high = float(bar.high)
        low = float(bar.low)

        # Detect new day — reset state
        if self._state.current_date is not None and bar_date != self._state.current_date:
            self._state = _RangeState()

        # Calculate the opening range window
        open_start = datetime.datetime(
            bar_date.year, bar_date.month, bar_date.day,
            self._market_open_hour_utc, 0, 0,
            tzinfo=datetime.timezone.utc,
        )
        open_end = open_start + datetime.timedelta(minutes=self._range_minutes)

        self._state.current_date = bar_date

        if self._state.locked:
            # Already locked — levels persist, nothing to do
            return

        if open_start <= dt < open_end:
            # Within the opening range window — track H/L
            if not self._state.has_data:
                self._state.high = high
                self._state.low = low
                self._state.range_start_ts = ts
                self._state.has_data = True
            else:
                self._state.high = max(self._state.high, high)
                self._state.low = min(self._state.low, low)
        elif dt >= open_end and self._state.has_data and not self._state.locked:
            # Past the range — lock levels
            self._state.locked = True
            self._emit_levels(ts)

    def _emit_levels(self, ts: int) -> None:
        self._levels = []
        for level_type, price in [("high", self._state.high), ("low", self._state.low)]:
            self._levels.append(
                KeyLevel(
                    price=price,
                    strength=0.8,
                    bounce_count=1,
                    first_seen_ts=self._state.range_start_ts,
                    last_touched_ts=ts,
                    zone_upper=price,
                    zone_lower=price,
                    source="opening_range",
                    meta=OpeningRangeMeta(
                        range_minutes=self._range_minutes,
                        level_type=level_type,
                    ),
                )
            )

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._state = _RangeState()
        self._levels = []
