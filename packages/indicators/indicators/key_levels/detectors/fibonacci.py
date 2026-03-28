"""Fibonacci level detectors — retracement and extension.

Retracement: Detects the most recent significant swing high/low pair
(ATR-filtered), then calculates Fibonacci retracement levels between them.

Extension: (To be added later.)
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import FibonacciMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import Swing, SwingDetector

RETRACEMENT_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)

_RATIO_STRENGTH: dict[float, float] = {
    0.618: 1.0,
    0.5: 0.8,
    0.382: 0.6,
    0.786: 0.5,
    0.236: 0.4,
}


class FibonacciRetracementDetector:
    """Detects Fibonacci retracement levels from the most recent swing high/low pair.

    Args:
        swing_period: Fractal lookback N for swing detection. Default 5.
        min_swing_atr_multiple: Minimum swing size as ATR multiple to qualify. Default 2.0.
        atr_period: ATR period. Default 14.
    """

    def __init__(
        self,
        swing_period: int = 5,
        min_swing_atr_multiple: float = 2.0,
        atr_period: int = 14,
    ) -> None:
        self._swing_period = swing_period
        self._min_swing_atr_multiple = min_swing_atr_multiple

        self._swing_detector = SwingDetector(period=swing_period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0
        self._levels: list[KeyLevel] = []

        self._last_swing_high: Swing | None = None
        self._last_swing_low: Swing | None = None

    @property
    def name(self) -> str:
        return "fib_retracement"

    @property
    def warmup_bars(self) -> int:
        return self._swing_period * 2 + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)

        self._atr.update(high, low, close)

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=bar.ts_event,
        )

        if swing is not None:
            if swing.side == "high":
                self._last_swing_high = swing
            else:
                self._last_swing_low = swing

        self._bar_index += 1

        if (
            self._atr.ready
            and self._last_swing_high is not None
            and self._last_swing_low is not None
        ):
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        sh = self._last_swing_high
        sl = self._last_swing_low
        assert sh is not None and sl is not None  # noqa: S101

        swing_range = abs(sh.price - sl.price)
        atr = self._atr.value

        if swing_range < self._min_swing_atr_multiple * atr:
            self._levels = []
            return

        # Determine trend direction by which swing came later
        uptrend = sl.bar_index < sh.bar_index
        most_recent_ts = max(sh.ts, sl.ts)
        half_zone = 0.15 * atr

        levels: list[KeyLevel] = []
        for ratio in RETRACEMENT_RATIOS:
            if uptrend:
                # Levels are support below the swing high
                level_price = sh.price - ratio * swing_range
            else:
                # Levels are resistance above the swing low
                level_price = sl.price + ratio * swing_range

            levels.append(
                KeyLevel(
                    price=level_price,
                    strength=_RATIO_STRENGTH[ratio],
                    bounce_count=0,
                    first_seen_ts=most_recent_ts,
                    last_touched_ts=most_recent_ts,
                    zone_upper=level_price + half_zone,
                    zone_lower=level_price - half_zone,
                    source="fib_retracement",
                    meta=FibonacciMeta(
                        ratio=ratio,
                        swing_high=sh.price,
                        swing_low=sl.price,
                        direction="retracement",
                    ),
                )
            )

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._levels = []
        self._last_swing_high = None
        self._last_swing_low = None
