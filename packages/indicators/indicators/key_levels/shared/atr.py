"""Streaming ATR (Average True Range) calculator.

Uses Wilder's smoothing: first ATR is a simple average of the first `period`
true ranges, then subsequent values use exponential smoothing:
    ATR = (prev_ATR * (period - 1) + current_TR) / period
"""

from __future__ import annotations


class StreamingAtr:

    def __init__(self, period: int = 14) -> None:
        self._period = period
        self._count: int = 0
        self._prev_close: float | None = None
        self._tr_sum: float = 0.0
        self._atr: float = 0.0
        self._ready: bool = False

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def value(self) -> float:
        return self._atr if self._ready else 0.0

    def update(self, high: float, low: float, close: float) -> None:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close),
            )

        self._prev_close = close
        self._count += 1

        if not self._ready:
            self._tr_sum += tr
            if self._count >= self._period:
                self._atr = self._tr_sum / self._period
                self._ready = True
        else:
            # Wilder's smoothing
            self._atr = (self._atr * (self._period - 1) + tr) / self._period

    def reset(self) -> None:
        self._count = 0
        self._prev_close = None
        self._tr_sum = 0.0
        self._atr = 0.0
        self._ready = False
