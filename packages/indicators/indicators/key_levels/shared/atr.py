"""Streaming Average True Range (ATR) calculator.

Uses Wilder smoothing: first ATR is the SMA of the first `period` true ranges,
then each subsequent ATR = (prev_atr * (period - 1) + current_tr) / period.
"""

from __future__ import annotations


class StreamingAtr:
    """Incrementally computes ATR using Wilder smoothing."""

    def __init__(self, period: int = 14) -> None:
        self._period = period
        self._count = 0
        self._prev_close: float | None = None
        self._tr_buffer: list[float] = []
        self._atr: float = 0.0
        self._ready = False

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
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))

        self._prev_close = close
        self._count += 1

        if not self._ready:
            self._tr_buffer.append(tr)
            if len(self._tr_buffer) == self._period:
                self._atr = sum(self._tr_buffer) / self._period
                self._ready = True
                self._tr_buffer.clear()
        else:
            self._atr = (self._atr * (self._period - 1) + tr) / self._period

    def reset(self) -> None:
        self._count = 0
        self._prev_close = None
        self._tr_buffer.clear()
        self._atr = 0.0
        self._ready = False
