"""Williams fractal swing detection.

A fractal high at bar[i] means bar[i].high is greater than the highs of
the `period` bars on each side. A fractal low is the mirror.

The detector has an inherent lag of `period` bars — a swing at bar[i]
can only be confirmed once bar[i + period] has been received.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Swing:
    price: float
    bar_index: int
    ts: int
    side: Literal["high", "low"]


class SwingDetector:
    """Detects fractal swing highs and lows with configurable lookback.

    Args:
        period: Number of bars on each side of the fractal center.
                Default Williams fractal uses period=2 (5-bar pattern).
    """

    def __init__(self, period: int = 2) -> None:
        self._period = period
        self._window_size = 2 * period + 1
        self._highs: deque[float] = deque(maxlen=self._window_size)
        self._lows: deque[float] = deque(maxlen=self._window_size)
        self._indices: deque[int] = deque(maxlen=self._window_size)
        self._timestamps: deque[int] = deque(maxlen=self._window_size)
        self._swings: list[Swing] = []

    @property
    def warmup_bars(self) -> int:
        return self._window_size

    def update(self, high: float, low: float, bar_index: int, ts: int) -> Swing | None:
        """Add a new bar and check if the center bar is a confirmed fractal.

        Returns the newly confirmed Swing if one was detected, else None.
        """
        self._highs.append(high)
        self._lows.append(low)
        self._indices.append(bar_index)
        self._timestamps.append(ts)

        if len(self._highs) < self._window_size:
            return None

        center = self._period
        center_high = self._highs[center]
        center_low = self._lows[center]

        detected: Swing | None = None

        # Check fractal high
        is_fractal_high = all(
            center_high > self._highs[j]
            for j in range(self._window_size)
            if j != center
        )
        if is_fractal_high:
            swing = Swing(
                price=center_high,
                bar_index=self._indices[center],
                ts=self._timestamps[center],
                side="high",
            )
            self._swings.append(swing)
            detected = swing

        # Check fractal low
        is_fractal_low = all(
            center_low < self._lows[j]
            for j in range(self._window_size)
            if j != center
        )
        if is_fractal_low:
            swing = Swing(
                price=center_low,
                bar_index=self._indices[center],
                ts=self._timestamps[center],
                side="low",
            )
            self._swings.append(swing)
            detected = swing

        return detected

    def swings(self) -> list[Swing]:
        return list(self._swings)

    def reset(self) -> None:
        self._highs.clear()
        self._lows.clear()
        self._indices.clear()
        self._timestamps.clear()
        self._swings.clear()
