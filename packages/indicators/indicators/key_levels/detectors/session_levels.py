"""SessionLevelDetector — track high and low of defined trading sessions.

Previous session's H/L become key levels. Each completed session produces
two levels (high + low).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, SessionLevelMeta


@dataclass
class _SessionTracker:
    """Mutable running state for a single session instance."""

    high: float = float("-inf")
    low: float = float("inf")
    active: bool = False
    session_date: datetime.date | None = None


class SessionLevelDetector:

    def __init__(
        self,
        sessions: dict[str, tuple[int, int]] | None = None,
        exchange_timezone: str = "UTC",
    ) -> None:
        self._sessions = sessions or {
            "asian": (0, 8),
            "london": (7, 16),
            "new_york": (12, 21),
        }
        self._exchange_timezone = exchange_timezone

        # Running trackers per session name
        self._trackers: dict[str, _SessionTracker] = {
            name: _SessionTracker() for name in self._sessions
        }

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "session_level"

    @property
    def warmup_bars(self) -> int:
        # Need enough bars to complete one session
        min_duration = min(
            (end - start) % 24 for start, end in self._sessions.values()
        )
        return max(1, min_duration)

    def update(self, bar: Bar) -> None:
        ts = bar.ts_event
        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        hour = dt.hour
        bar_date = dt.date()
        high = float(bar.high)
        low = float(bar.low)

        for session_name, (start_hour, end_hour) in self._sessions.items():
            tracker = self._trackers[session_name]

            in_session = start_hour <= hour < end_hour

            if in_session:
                if not tracker.active:
                    # Starting a new session instance
                    tracker.active = True
                    tracker.high = high
                    tracker.low = low
                    tracker.session_date = bar_date
                else:
                    tracker.high = max(tracker.high, high)
                    tracker.low = min(tracker.low, low)
            else:
                # Outside session — if we were active, the session just ended
                if tracker.active:
                    self._emit_levels(session_name, tracker, ts)
                    # Reset tracker
                    tracker.active = False
                    tracker.high = float("-inf")
                    tracker.low = float("inf")
                    tracker.session_date = None

    def _emit_levels(
        self, session_name: str, tracker: _SessionTracker, ts: int
    ) -> None:
        session_date = tracker.session_date or datetime.date(2000, 1, 1)

        # Remove previous levels for this session
        self._levels = [
            lv
            for lv in self._levels
            if not (
                isinstance(lv.meta, SessionLevelMeta)
                and lv.meta.session == session_name
            )
        ]

        for level_type, price in [("high", tracker.high), ("low", tracker.low)]:
            self._levels.append(
                KeyLevel(
                    price=price,
                    strength=0.7,
                    bounce_count=1,
                    first_seen_ts=ts,
                    last_touched_ts=ts,
                    zone_upper=price,
                    zone_lower=price,
                    source="session_level",
                    meta=SessionLevelMeta(
                        session=session_name,
                        level_type=level_type,
                        session_date=session_date,
                    ),
                )
            )

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._trackers = {
            name: _SessionTracker() for name in self._sessions
        }
        self._levels = []
