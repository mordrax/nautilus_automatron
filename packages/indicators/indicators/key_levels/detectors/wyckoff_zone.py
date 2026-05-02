"""WyckoffZoneDetector — lifecycle-tracked accumulation / distribution zones.

The classical Wyckoff phase model (PS/SC/AR/ST/SOS/LPS for accumulation,
PSY/BC/AR/ST/SOW/LPSY for distribution) is heuristic and noisy to fit on raw
OHLCV. This detector uses a simplified, deterministic heuristic that captures
the same essential lifecycle:

1. **Trend detection** — track the close-vs-prior swing extreme over a
   ``trend_lookback`` window; a strong move down → potential accumulation,
   strong move up → potential distribution.
2. **Range collapse (Phase A confirmation)** — wait for ``min_range_bars`` of
   bars whose true range collapses to ``range_atr_multiple * ATR`` or tighter.
   That sideways "rest" after the drive is the Wyckoff Phase A range. We emit
   the zone at this point with phase ``A``.
3. **Phase progression** — as long as price stays inside the zone, advance
   the phase (B, C, D) heuristically based on the number of bars elapsed.
   This is informational metadata only — the lifecycle hinges on the breakout
   check.
4. **End** — when close moves beyond the zone bounds by
   ``breakout_atr * ATR`` (Phase E breakout / breakdown), the zone is
   finalized. Aged-out zones (no in-range touch for ``max_idle_bars``) also
   end.

`side` is "low" for accumulation (a future support floor) and "high" for
distribution (a future resistance ceiling). `bounce_count` increments on bars
that pierce the zone but close back inside (Wyckoff "tests"); `touch_count`
on every bar overlapping the zone.

Notes on simplification: the explicit AR/ST/SOS/LPSY events from the original
prototype are not detected here. Instead we use range-collapse-after-drive as
a proxy for Phase A confirmation. This is documented in the docstring.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, WyckoffZoneMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedZone:
    id: int
    zone_type: Literal["accumulation", "distribution"]
    side: Literal["high", "low"]
    zone_upper: float
    zone_lower: float
    start_ts: int
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_in_zone: int
    confidence: float
    phase: Literal["A", "B", "C", "D", "E"]


class WyckoffZoneDetector:

    def __init__(
        self,
        trend_lookback: int = 30,
        trend_atr_multiple: float = 3.0,
        min_range_bars: int = 6,
        range_atr_multiple: float = 1.5,
        atr_period: int = 14,
        breakout_atr: float = 1.0,
        breakout_consecutive_bars: int = 2,
        max_idle_bars: int = 200,
        phase_b_bars: int = 10,
        phase_c_bars: int = 20,
        phase_d_bars: int = 30,
    ) -> None:
        self._trend_lookback = trend_lookback
        self._trend_atr_multiple = trend_atr_multiple
        self._min_range_bars = min_range_bars
        self._range_atr_multiple = range_atr_multiple
        self._breakout_atr = breakout_atr
        self._breakout_consecutive_bars = breakout_consecutive_bars
        self._max_idle_bars = max_idle_bars
        self._phase_b_bars = phase_b_bars
        self._phase_c_bars = phase_c_bars
        self._phase_d_bars = phase_d_bars

        self._atr = StreamingAtr(period=atr_period)
        self._closes: deque[float] = deque(maxlen=trend_lookback)
        self._highs: deque[float] = deque(maxlen=trend_lookback)
        self._lows: deque[float] = deque(maxlen=trend_lookback)
        self._range_buffer_high: deque[float] = deque(maxlen=min_range_bars)
        self._range_buffer_low: deque[float] = deque(maxlen=min_range_bars)

        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None
        self._bars_through: int = 0

        self._tracked: list[_TrackedZone] = []
        self._next_id: int = 0
        self._active_id: int | None = None

    @property
    def name(self) -> str:
        return "wyckoff_zone"

    @property
    def warmup_bars(self) -> int:
        return max(self._trend_lookback, self._min_range_bars)

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

        # Lifecycle on existing active zone.
        active = self._get_active()
        if active is not None:
            self._apply_bar_to_zone(active, high, low, close, ts)

        # Try to emit a new zone if no active.
        if self._get_active() is None and self._atr.ready:
            self._try_emit(high, low, close, ts)

        # Update rolling buffers AFTER detection so the current bar contributes
        # to next bar's range/trend calc.
        self._closes.append(close)
        self._highs.append(high)
        self._lows.append(low)
        self._range_buffer_high.append(high)
        self._range_buffer_low.append(low)

    def _get_active(self) -> _TrackedZone | None:
        if self._active_id is None:
            return None
        zone = self._tracked[self._active_id]
        if zone.end_ts is not None:
            self._active_id = None
            return None
        return zone

    def _apply_bar_to_zone(
        self,
        zone: _TrackedZone,
        high: float,
        low: float,
        close: float,
        ts: int,
    ) -> None:
        atr_value = self._atr.value
        breakout_dist = self._breakout_atr * atr_value

        # Bar overlap with zone → touch.
        if low <= zone.zone_upper and high >= zone.zone_lower:
            zone.touch_count += 1
            zone.last_touch_ts = ts
            zone.bars_in_zone += 1

            # Wick test: high pierces above (or low pierces below) but close
            # back inside → Wyckoff "test".
            pierced = (
                high > zone.zone_upper or low < zone.zone_lower
            )
            inside = zone.zone_lower <= close <= zone.zone_upper
            if pierced and inside:
                zone.bounce_count += 1

        # Phase progression (informational).
        if zone.bars_in_zone >= self._phase_d_bars:
            zone.phase = "D"
        elif zone.bars_in_zone >= self._phase_c_bars:
            zone.phase = "C"
        elif zone.bars_in_zone >= self._phase_b_bars:
            zone.phase = "B"

        # Breakout check (Phase E).
        if zone.zone_type == "accumulation":
            beyond = close > zone.zone_upper + breakout_dist
        else:
            beyond = close < zone.zone_lower - breakout_dist

        if beyond:
            self._bars_through += 1
        else:
            self._bars_through = 0

        if self._bars_through >= self._breakout_consecutive_bars:
            zone.phase = "E"
            zone.end_ts = ts
            self._bars_through = 0
            self._active_id = None
            return

        # Aged-out.
        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - zone.last_touch_ts > idle_ns:
            zone.end_ts = zone.last_touch_ts
            self._active_id = None

    def _try_emit(
        self,
        high: float,
        low: float,
        close: float,
        ts: int,
    ) -> None:
        if (
            len(self._closes) < self._trend_lookback
            or len(self._range_buffer_high) < self._min_range_bars
        ):
            return

        atr_value = self._atr.value
        if atr_value <= 0:
            return

        # Range collapse: the last `min_range_bars` (including the current bar
        # via direct high/low) span < range_atr_multiple * ATR.
        recent_high = max(max(self._range_buffer_high), high)
        recent_low = min(min(self._range_buffer_low), low)
        range_span = recent_high - recent_low
        if range_span > self._range_atr_multiple * atr_value:
            return

        # Trend detection: compare the start of the lookback window to the
        # current close.
        first_close = self._closes[0]
        move = close - first_close
        threshold = self._trend_atr_multiple * atr_value

        if move <= -threshold:
            zone_type: Literal["accumulation", "distribution"] = "accumulation"
            side: Literal["high", "low"] = "low"
        elif move >= threshold:
            zone_type = "distribution"
            side = "high"
        else:
            return

        # Confidence: how far the trend pushed beyond the threshold,
        # normalized; capped at 1.
        excess = abs(move) - threshold
        confidence = min(1.0, 0.5 + excess / (threshold if threshold > 0 else 1.0) * 0.5)

        zone = _TrackedZone(
            id=self._next_id,
            zone_type=zone_type,
            side=side,
            zone_upper=recent_high,
            zone_lower=recent_low,
            start_ts=ts,
            end_ts=None,
            bounce_count=0,
            touch_count=1,
            last_touch_ts=ts,
            bars_in_zone=1,
            confidence=confidence,
            phase="A",
        )
        self._tracked.append(zone)
        self._active_id = zone.id
        self._next_id += 1

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for zone in self._tracked:
            midpoint = 0.5 * (zone.zone_upper + zone.zone_lower)
            # Strength tied to confidence + accumulated tests.
            test_bonus = min(0.3, 0.1 * zone.bounce_count)
            strength = max(0.0, min(1.0, zone.confidence + test_bonus))

            out.append(KeyLevel(
                price=midpoint,
                strength=strength,
                start_ts=zone.start_ts,
                end_ts=zone.end_ts,
                source="wyckoff_zone",
                bounce_count=zone.bounce_count,
                zone_upper=zone.zone_upper,
                zone_lower=zone.zone_lower,
                meta=WyckoffZoneMeta(
                    zone_type=zone.zone_type,
                    phase=zone.phase,
                    confidence=zone.confidence,
                    side=zone.side,
                    touch_count=zone.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._closes.clear()
        self._highs.clear()
        self._lows.clear()
        self._range_buffer_high.clear()
        self._range_buffer_low.clear()
        self._last_bar_ts = None
        self._bar_interval_ns = None
        self._bars_through = 0
        self._tracked.clear()
        self._next_id = 0
        self._active_id = None
