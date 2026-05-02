"""SessionLevelDetector — Asian / London / NY session highs and lows
(lifecycle-tracked).

Each completed session emits two levels (high & low). Levels are born at
session end with the final session high/low and live until they are broken
(close beyond by ``break_atr_multiple`` x ATR for ``break_consecutive_bars``)
or aged out (no touch for ``max_idle_bars`` bars).

`bounce_count` is initialized to 1 (the session itself) and increments on
swing-pivot touches; `touch_count` increments on bar-level overlaps with the
tolerance band around the level.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, SessionLevelMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector

SessionName = Literal["asian", "london", "new_york"]


@dataclass
class _SessionAccumulator:
    """Mutable running state for a single session instance."""

    high: float = float("-inf")
    low: float = float("inf")
    active: bool = False
    session_date: datetime.date | None = None


@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    role: Literal["high", "low"]
    centroid: float
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int
    session_name: SessionName
    session_date_iso: str


class SessionLevelDetector:

    def __init__(
        self,
        sessions: dict[SessionName, tuple[int, int]] | None = None,
        atr_period: int = 14,
        swing_period: int = 2,
        break_atr_multiple: float = 1.0,
        break_consecutive_bars: int = 2,
        # Sessions are typically valid across multiple days.
        max_idle_bars: int = 1000,
        strength_decay_k: float = 3.0,
        min_touches: int = 1,
    ) -> None:
        self._sessions: dict[SessionName, tuple[int, int]] = sessions or {
            "asian": (0, 8),
            "london": (7, 16),
            "new_york": (12, 21),
        }
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

        self._accumulators: dict[SessionName, _SessionAccumulator] = {
            name: _SessionAccumulator() for name in self._sessions
        }

        self._tracked: list[_TrackedLevel] = []
        self._next_id: int = 0

    @property
    def name(self) -> str:
        return "session_level"

    @property
    def warmup_bars(self) -> int:
        return 1

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

        # Per-bar lifecycle on tracked levels.
        if self._atr.ready:
            tolerance = 0.25 * self._atr.value
            for lvl in self._tracked:
                if lvl.end_ts is None:
                    self._apply_bar_to_level(lvl, high, low, close, ts, tolerance)
            if swing is not None:
                for lvl in self._tracked:
                    if lvl.end_ts is not None or lvl.side != swing.side:
                        continue
                    if abs(swing.price - lvl.centroid) <= tolerance:
                        lvl.bounce_count += 1
                        lvl.last_touch_ts = swing.ts

        # Session accumulation.
        dt = datetime.datetime.fromtimestamp(ts / 1e9, tz=datetime.timezone.utc)
        hour = dt.hour
        bar_date = dt.date()

        for session_name, (start_hour, end_hour) in self._sessions.items():
            acc = self._accumulators[session_name]
            in_session = start_hour <= hour < end_hour

            if in_session:
                if not acc.active:
                    acc.active = True
                    acc.high = high
                    acc.low = low
                    acc.session_date = bar_date
                else:
                    acc.high = max(acc.high, high)
                    acc.low = min(acc.low, low)
            else:
                if acc.active:
                    self._emit_session_levels(session_name, acc, ts)
                    acc.active = False
                    acc.high = float("-inf")
                    acc.low = float("inf")
                    acc.session_date = None

    def _emit_session_levels(
        self,
        session_name: SessionName,
        acc: _SessionAccumulator,
        ts: int,
    ) -> None:
        session_date = acc.session_date or datetime.date(2000, 1, 1)
        date_iso = session_date.isoformat()

        for role, price in (("high", acc.high), ("low", acc.low)):
            self._tracked.append(_TrackedLevel(
                id=self._next_id,
                side=role,  # type: ignore[arg-type]
                role=role,  # type: ignore[arg-type]
                centroid=price,
                start_ts=ts,
                end_ts=None,
                bounce_count=1,
                touch_count=0,
                last_touch_ts=ts,
                bars_through=0,
                session_name=session_name,
                session_date_iso=date_iso,
            ))
            self._next_id += 1

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
            strength = max(0.0, min(1.0, 0.7 * decay))

            out.append(KeyLevel(
                price=lvl.centroid,
                strength=strength,
                start_ts=lvl.start_ts,
                end_ts=lvl.end_ts,
                source="session_level",
                bounce_count=lvl.bounce_count,
                zone_upper=lvl.centroid,
                zone_lower=lvl.centroid,
                meta=SessionLevelMeta(
                    session=lvl.session_name,
                    role=lvl.role,
                    session_date_iso=lvl.session_date_iso,
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
        self._accumulators = {
            name: _SessionAccumulator() for name in self._sessions
        }
        self._tracked.clear()
        self._next_id = 0
