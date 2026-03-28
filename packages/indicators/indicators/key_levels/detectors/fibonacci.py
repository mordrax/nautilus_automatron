"""Fibonacci level detectors — retracement and extension.

Retracement: Detects the most recent significant swing high/low pair
(ATR-filtered), then calculates Fibonacci retracement levels between them.

Extension: Projects Fibonacci extension levels beyond point C of an A-B-C
swing pattern at standard ratios (100%, 127.2%, 161.8%, 200%, 261.8%).
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


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

EXTENSION_RATIOS = (1.0, 1.272, 1.618, 2.0, 2.618)

_EXT_RATIO_STRENGTH: dict[float, float] = {
    1.618: 1.0,
    1.0: 0.8,
    1.272: 0.7,
    2.0: 0.6,
    2.618: 0.5,
}


class FibonacciExtensionDetector:
    """Detects Fibonacci extension levels from a 3-point swing pattern (A-B-C).

    Given three points — swing A, swing B, retracement C — project extension
    levels beyond C at ratios: 100%, 127.2%, 161.8%, 200%, 261.8%.

    Args:
        swing_period: Fractal lookback N. Default 5.
        min_swing_atr_multiple: Minimum swing size as ATR multiple. Default 2.0.
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
        self._swings: list[Swing] = []

    @property
    def name(self) -> str:
        return "fib_extension"

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
            self._swings.append(swing)

        self._bar_index += 1

        if self._atr.ready and len(self._swings) >= 3:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        a, b, c = self._swings[-3], self._swings[-2], self._swings[-1]
        atr = self._atr.value

        # Determine pattern: low-high-low (uptrend) or high-low-high (downtrend)
        if a.side == "low" and b.side == "high" and c.side == "low":
            uptrend = True
        elif a.side == "high" and b.side == "low" and c.side == "high":
            uptrend = False
        else:
            # Not a valid A-B-C pattern
            self._levels = []
            return

        swing_range = abs(b.price - a.price)
        if swing_range < self._min_swing_atr_multiple * atr:
            self._levels = []
            return

        most_recent_ts = max(a.ts, b.ts, c.ts)
        half_zone = 0.15 * atr
        swing_high = max(a.price, b.price, c.price)
        swing_low = min(a.price, b.price, c.price)

        levels: list[KeyLevel] = []
        for ratio in EXTENSION_RATIOS:
            if uptrend:
                ext_price = c.price + ratio * (b.price - a.price)
            else:
                ext_price = c.price - ratio * (a.price - b.price)

            levels.append(
                KeyLevel(
                    price=ext_price,
                    strength=_EXT_RATIO_STRENGTH[ratio],
                    bounce_count=0,
                    first_seen_ts=most_recent_ts,
                    last_touched_ts=most_recent_ts,
                    zone_upper=ext_price + half_zone,
                    zone_lower=ext_price - half_zone,
                    source="fib_extension",
                    meta=FibonacciMeta(
                        ratio=ratio,
                        swing_high=swing_high,
                        swing_low=swing_low,
                        direction="extension",
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
        self._swings = []
