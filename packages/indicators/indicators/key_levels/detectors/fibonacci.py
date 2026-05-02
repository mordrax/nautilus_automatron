"""Fibonacci level detectors — STUB.

Original snapshot-based implementations were removed in the KeyLevel
event-model slice (#118) because they construct `KeyLevel` with the old
`first_seen_ts` / `last_touched_ts` shape.

# TODO(card #120): migrate retracement + extension detectors to event-based
# KeyLevel — each Fib set becomes a group of lifecycle-tracked levels born on
# swing confirmation and aged out when a new swing supersedes them.

These stubs keep the import surface stable. They produce no levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel

RETRACEMENT_RATIOS = (0.236, 0.382, 0.5, 0.618, 0.786)


class FibonacciRetracementDetector:

    def __init__(
        self,
        swing_period: int = 5,
        min_swing_atr_multiple: float = 2.0,
        atr_period: int = 14,
    ) -> None:
        self._swing_period = swing_period
        self._min_swing_atr_multiple = min_swing_atr_multiple
        self._atr_period = atr_period

    @property
    def name(self) -> str:
        return "fib_retracement"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._swing_period + 1

    def update(self, bar: Bar) -> None:
        return None

    def levels(self) -> list[KeyLevel]:
        return []

    def reset(self) -> None:
        return None


class FibonacciExtensionDetector:

    def __init__(
        self,
        swing_period: int = 5,
        min_swing_atr_multiple: float = 2.0,
        atr_period: int = 14,
    ) -> None:
        self._swing_period = swing_period
        self._min_swing_atr_multiple = min_swing_atr_multiple
        self._atr_period = atr_period

    @property
    def name(self) -> str:
        return "fib_extension"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._swing_period + 1

    def update(self, bar: Bar) -> None:
        return None

    def levels(self) -> list[KeyLevel]:
        return []

    def reset(self) -> None:
        return None
