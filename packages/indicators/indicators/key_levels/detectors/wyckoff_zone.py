"""WyckoffZoneDetector — detect individual Wyckoff events as key levels.

Detects four event types based on price action and volume:
- Selling Climax (SC): large bearish bar with extreme volume
- Spring: false breakdown below recent lows with low volume
- Buying Climax (BC): large bullish bar with extreme volume
- Upthrust: false breakout above recent highs with low volume

Each detected event creates a zone from the event bar's full range.
"""

from __future__ import annotations

from collections import deque

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, WyckoffZoneMeta
from indicators.key_levels.shared.atr import StreamingAtr


class WyckoffZoneDetector:

    def __init__(
        self,
        volume_period: int = 20,
        swing_period: int = 10,
        atr_period: int = 14,
        max_age_bars: int = 200,
    ) -> None:
        self._volume_period = volume_period
        self._swing_period = swing_period
        self._atr_period = atr_period
        self._max_age_bars = max_age_bars

        self._atr = StreamingAtr(period=atr_period)
        self._volume_buffer: deque[float] = deque(maxlen=volume_period)

        # Rolling windows for swing high/low lookback
        self._high_buffer: deque[float] = deque(maxlen=swing_period)
        self._low_buffer: deque[float] = deque(maxlen=swing_period)

        self._bar_index: int = 0

        # Stored events: (event_type, bar_index, ts, high, low, midpoint)
        self._events: list[tuple[str, int, int, float, float, float]] = []
        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "wyckoff_zone"

    @property
    def warmup_bars(self) -> int:
        return max(self._volume_period, self._swing_period)

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        open_ = float(bar.open)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        # Check for events before updating buffers (need prior N bars)
        if (
            self._atr.ready
            and len(self._volume_buffer) == self._volume_period
            and len(self._high_buffer) == self._swing_period
        ):
            avg_vol = sum(self._volume_buffer) / len(self._volume_buffer)
            atr = self._atr.value
            body = abs(close - open_)
            lowest_low = min(self._low_buffer)
            highest_high = max(self._high_buffer)

            # Selling Climax: bearish bar, body > 2*ATR, volume > 2x avg
            if close < open_ and body > 2.0 * atr and volume > 2.0 * avg_vol:
                self._events.append(("sc", self._bar_index, ts, high, low, (high + low) / 2.0))

            # Buying Climax: bullish bar, body > 2*ATR, volume > 2x avg
            if close > open_ and body > 2.0 * atr and volume > 2.0 * avg_vol:
                self._events.append(("bc", self._bar_index, ts, high, low, (high + low) / 2.0))

            # Spring: dips below lowest low then closes back above, low volume
            if low < lowest_low and close > lowest_low and volume < 0.5 * avg_vol:
                self._events.append(("spring", self._bar_index, ts, high, low, (high + low) / 2.0))

            # Upthrust: rises above highest high then closes back below, low volume
            if high > highest_high and close < highest_high and volume < 0.5 * avg_vol:
                self._events.append(("upthrust", self._bar_index, ts, high, low, (high + low) / 2.0))

        # Update buffers after event detection
        self._volume_buffer.append(volume)
        self._high_buffer.append(high)
        self._low_buffer.append(low)

        self._bar_index += 1

        # Purge old events and rebuild levels
        self._events = [
            e for e in self._events if self._bar_index - e[1] <= self._max_age_bars
        ]
        self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        levels: list[KeyLevel] = []
        for event_type, bar_idx, ts, zone_high, zone_low, midpoint in self._events:
            age = self._bar_index - bar_idx
            base_strength = 0.9 if event_type in ("sc", "bc") else 0.7
            # Linear decay with age
            decay = max(0.0, 1.0 - age / self._max_age_bars)
            strength = base_strength * decay

            phase = "accumulation" if event_type in ("sc", "spring") else "distribution"

            levels.append(KeyLevel(
                price=midpoint,
                strength=strength,
                bounce_count=1,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=zone_high,
                zone_lower=zone_low,
                source="wyckoff_zone",
                meta=WyckoffZoneMeta(
                    phase=phase,
                    event=event_type,
                    zone_high=zone_high,
                    zone_low=zone_low,
                ),
            ))
        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._volume_buffer.clear()
        self._high_buffer.clear()
        self._low_buffer.clear()
        self._bar_index = 0
        self._events.clear()
        self._levels = []
