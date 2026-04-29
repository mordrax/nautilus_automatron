"""ConsolidationZoneDetector — horizontal price ranges via slope + volatility.

Detects consolidation by checking that the linear regression slope of a
rolling window of highs/lows is near-zero AND ATR is compressed relative
to a longer-term average.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, ConsolidationZoneMeta
from indicators.key_levels.shared.atr import StreamingAtr


def _linear_slope(values: list[float]) -> float:
    """Compute linear regression slope normalized by mean.

    Returns slope / mean so that the result is scale-independent.
    """
    n = len(values)
    if n < 2:
        return 0.0
    mean_y = sum(values) / n
    if mean_y == 0:
        return 0.0
    mean_x = (n - 1) / 2.0
    num = 0.0
    den = 0.0
    for i, y in enumerate(values):
        dx = i - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    if den == 0:
        return 0.0
    raw_slope = num / den
    return raw_slope / mean_y


@dataclass
class _TrackedZone:
    range_high: float
    range_low: float
    slope: float
    bar_count: int
    ts: int


class ConsolidationZoneDetector:

    def __init__(
        self,
        min_range_bars: int = 20,
        max_slope: float = 0.001,
        volatility_threshold: float = 0.5,
        atr_period: int = 14,
    ) -> None:
        self._min_range_bars = min_range_bars
        self._max_slope = max_slope
        self._volatility_threshold = volatility_threshold
        self._atr_period = atr_period

        self._atr = StreamingAtr(period=atr_period)
        self._long_atr = StreamingAtr(period=atr_period * 3)

        self._highs: deque[float] = deque(maxlen=min_range_bars)
        self._lows: deque[float] = deque(maxlen=min_range_bars)

        self._zone: _TrackedZone | None = None

    @property
    def name(self) -> str:
        return "consolidation_zone"

    @property
    def warmup_bars(self) -> int:
        return max(self._min_range_bars, self._atr_period * 3)

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)
        self._long_atr.update(high, low, close)

        self._highs.append(high)
        self._lows.append(low)

        if len(self._highs) < self._min_range_bars:
            return
        if not self._atr.ready or not self._long_atr.ready:
            return

        highs_list = list(self._highs)
        lows_list = list(self._lows)

        slope_high = _linear_slope(highs_list)
        slope_low = _linear_slope(lows_list)
        avg_slope = (abs(slope_high) + abs(slope_low)) / 2.0

        # Check volatility compression: current ATR vs longer-term ATR
        long_atr = self._long_atr.value
        if long_atr <= 0:
            return
        vol_ratio = self._atr.value / long_atr

        if avg_slope <= self._max_slope and vol_ratio <= self._volatility_threshold:
            range_high = max(highs_list)
            range_low = min(lows_list)
            self._zone = _TrackedZone(
                range_high=range_high,
                range_low=range_low,
                slope=avg_slope,
                bar_count=len(highs_list),
                ts=ts,
            )
        else:
            self._zone = None

    def levels(self) -> list[KeyLevel]:
        if self._zone is None:
            return []

        zone = self._zone
        strength = min(1.0, max(0.0, zone.bar_count / self._min_range_bars))

        return [
            KeyLevel(
                price=zone.range_high,
                strength=strength,
                bounce_count=1,
                first_seen_ts=zone.ts,
                last_touched_ts=zone.ts,
                zone_upper=zone.range_high,
                zone_lower=zone.range_low,
                source="consolidation_zone",
                meta=ConsolidationZoneMeta(
                    range_high=zone.range_high,
                    range_low=zone.range_low,
                    slope=zone.slope,
                    bar_count=zone.bar_count,
                ),
            ),
            KeyLevel(
                price=zone.range_low,
                strength=strength,
                bounce_count=1,
                first_seen_ts=zone.ts,
                last_touched_ts=zone.ts,
                zone_upper=zone.range_high,
                zone_lower=zone.range_low,
                source="consolidation_zone",
                meta=ConsolidationZoneMeta(
                    range_high=zone.range_high,
                    range_low=zone.range_low,
                    slope=zone.slope,
                    bar_count=zone.bar_count,
                ),
            ),
        ]

    def reset(self) -> None:
        self._atr.reset()
        self._long_atr.reset()
        self._highs.clear()
        self._lows.clear()
        self._zone = None
