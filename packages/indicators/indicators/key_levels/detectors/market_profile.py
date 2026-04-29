"""MarketProfileDetector — Time Price Opportunity (TPO) analysis.

Divides each session into time slices, tracks which price bins were visited
during each slice. POC (Point of Control) is the bin with the most TPO counts.
Value Area expands from POC until value_area_pct of total TPOs are captured.

Previous session's POC and VA boundaries become key levels for the current
session.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, MarketProfileMeta


@dataclass
class _SessionProfile:
    """Mutable accumulator for one session's TPO data."""

    session_high: float = float("-inf")
    session_low: float = float("inf")
    # price_bin_index -> count of time slices that visited it
    tpo_counts: dict[int, int] = field(default_factory=dict)
    last_slice_key: int | None = None
    total_tpo_periods: int = 0
    session_date: datetime.date | None = None
    has_data: bool = False


def _bin_index(price: float, session_low: float, bin_size: float) -> int:
    """Map a price to its bin index."""
    if bin_size <= 0:
        return 0
    return int((price - session_low) / bin_size)


class MarketProfileDetector:

    def __init__(
        self,
        slice_minutes: int = 30,
        bin_count: int = 50,
        value_area_pct: float = 0.7,
        session_start_hour_utc: int = 0,
        session_end_hour_utc: int = 24,
    ) -> None:
        self._slice_minutes = slice_minutes
        self._bin_count = bin_count
        self._value_area_pct = value_area_pct
        self._session_start_hour_utc = session_start_hour_utc
        self._session_end_hour_utc = session_end_hour_utc

        self._current_profile = _SessionProfile()
        self._prev_profile: _SessionProfile | None = None
        self._current_session_date: datetime.date | None = None

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "market_profile_tpo"

    @property
    def warmup_bars(self) -> int:
        return 1

    def _in_session(self, hour: int) -> bool:
        if self._session_start_hour_utc < self._session_end_hour_utc:
            return self._session_start_hour_utc <= hour < self._session_end_hour_utc
        # Wrapping session (e.g., 18-17 = nearly 24h)
        return hour >= self._session_start_hour_utc or hour < self._session_end_hour_utc

    def _slice_key(self, dt: datetime.datetime) -> int:
        """Return a key that changes each slice_minutes within a day."""
        minutes_since_midnight = dt.hour * 60 + dt.minute
        return minutes_since_midnight // self._slice_minutes

    def update(self, bar: Bar) -> None:
        ts = bar.ts_event
        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        bar_date = dt.date()
        hour = dt.hour
        high = float(bar.high)
        low = float(bar.low)

        # Detect new session (new date)
        if (
            self._current_session_date is not None
            and bar_date != self._current_session_date
        ):
            # Finalize previous session and compute levels
            if self._current_profile.has_data:
                self._prev_profile = self._current_profile
                self._rebuild_levels(ts)
            self._current_profile = _SessionProfile()

        self._current_session_date = bar_date

        if not self._in_session(hour):
            return

        profile = self._current_profile

        # Track session range
        if not profile.has_data:
            profile.session_high = high
            profile.session_low = low
            profile.session_date = bar_date
            profile.has_data = True
        else:
            profile.session_high = max(profile.session_high, high)
            profile.session_low = min(profile.session_low, low)

        # Determine which time slice this bar belongs to
        slice_key = self._slice_key(dt)
        if slice_key != profile.last_slice_key:
            profile.total_tpo_periods += 1
            profile.last_slice_key = slice_key

        # Compute bin size from current session range
        session_range = profile.session_high - profile.session_low
        if session_range <= 0:
            return

        bin_size = session_range / self._bin_count

        # Mark all bins that this bar's range touches
        low_bin = _bin_index(low, profile.session_low, bin_size)
        high_bin = _bin_index(high, profile.session_low, bin_size)
        # Clamp
        low_bin = max(0, low_bin)
        high_bin = min(self._bin_count - 1, high_bin)

        for b in range(low_bin, high_bin + 1):
            profile.tpo_counts[b] = profile.tpo_counts.get(b, 0) + 1

    def _rebuild_levels(self, ts: int) -> None:
        """Compute POC and Value Area from the previous session's profile."""
        profile = self._prev_profile
        if profile is None or not profile.has_data or not profile.tpo_counts:
            self._levels = []
            return

        session_range = profile.session_high - profile.session_low
        if session_range <= 0:
            self._levels = []
            return

        bin_size = session_range / self._bin_count

        # Find POC — bin with highest TPO count
        poc_bin = max(profile.tpo_counts, key=profile.tpo_counts.get)  # type: ignore[arg-type]
        poc_price = profile.session_low + (poc_bin + 0.5) * bin_size
        poc_count = profile.tpo_counts[poc_bin]

        # Compute Value Area: expand from POC bin outward
        total_tpo = sum(profile.tpo_counts.values())
        target_tpo = total_tpo * self._value_area_pct

        va_bins = {poc_bin}
        accumulated = profile.tpo_counts[poc_bin]

        lower_edge = poc_bin - 1
        upper_edge = poc_bin + 1

        while accumulated < target_tpo:
            lower_count = profile.tpo_counts.get(lower_edge, 0) if lower_edge >= 0 else 0
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

        self._levels = [
            KeyLevel(
                price=poc_price,
                strength=0.9,
                bounce_count=1,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=poc_price,
                zone_lower=poc_price,
                source="market_profile_tpo",
                meta=MarketProfileMeta(
                    tpo_count=poc_count,
                    node_type="poc",
                    total_tpo_periods=profile.total_tpo_periods,
                ),
            ),
            KeyLevel(
                price=va_high_price,
                strength=0.7,
                bounce_count=1,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=va_high_price,
                zone_lower=va_high_price,
                source="market_profile_tpo",
                meta=MarketProfileMeta(
                    tpo_count=sum(
                        profile.tpo_counts.get(b, 0) for b in va_bins
                    ),
                    node_type="va_high",
                    total_tpo_periods=profile.total_tpo_periods,
                ),
            ),
            KeyLevel(
                price=va_low_price,
                strength=0.7,
                bounce_count=1,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=va_low_price,
                zone_lower=va_low_price,
                source="market_profile_tpo",
                meta=MarketProfileMeta(
                    tpo_count=sum(
                        profile.tpo_counts.get(b, 0) for b in va_bins
                    ),
                    node_type="va_low",
                    total_tpo_periods=profile.total_tpo_periods,
                ),
            ),
        ]

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._current_profile = _SessionProfile()
        self._prev_profile = None
        self._current_session_date = None
        self._levels = []
