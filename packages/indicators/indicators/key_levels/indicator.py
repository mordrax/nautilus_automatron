"""KeyLevelIndicator — NautilusTrader Indicator subclass.

Composes multiple KeyLevelDetectors and exposes dual output paths:
- .levels -> list[KeyLevel] for strategy consumption
- Scalar summary properties for dashboard/registry integration
"""

from __future__ import annotations

from nautilus_trader.indicators.base import Indicator
from nautilus_trader.model.data import Bar

from indicators.key_levels.detector import KeyLevelDetector
from indicators.key_levels.model import KeyLevel, Source


class KeyLevelIndicator(Indicator):

    def __init__(
        self,
        detectors: list[KeyLevelDetector],
        max_levels: int = 200,
    ) -> None:
        super().__init__([d.name for d in detectors])
        self._detectors = detectors
        self._max_levels = max_levels
        self._levels: list[KeyLevel] = []
        self._current_price: float = 0.0
        self._bar_count: int = 0
        self._max_warmup: int = max(
            (d.warmup_bars for d in detectors), default=0
        )

    def handle_bar(self, bar: Bar) -> None:
        self._set_has_inputs(True)
        self._bar_count += 1
        self._current_price = float(bar.close)

        for detector in self._detectors:
            detector.update(bar)

        # Merge all detector levels (no deduplication — confluence is signal)
        self._levels = []
        for detector in self._detectors:
            self._levels.extend(detector.levels())

        # Sort by strength descending
        self._levels.sort(key=lambda lvl: lvl.strength, reverse=True)

        # Enforce max levels
        if len(self._levels) > self._max_levels:
            self._levels = self._levels[: self._max_levels]

        # Initialize once all detectors have seen enough bars
        if not self.initialized and self._bar_count >= self._max_warmup:
            self._set_initialized(True)

    # -- Full collection output (for strategies) --

    @property
    def levels(self) -> list[KeyLevel]:
        return self._levels

    def levels_above(self, price: float) -> list[KeyLevel]:
        return [lvl for lvl in self._levels if lvl.price > price]

    def levels_below(self, price: float) -> list[KeyLevel]:
        return [lvl for lvl in self._levels if lvl.price < price]

    def levels_by_source(self, source: Source) -> list[KeyLevel]:
        return [lvl for lvl in self._levels if lvl.source == source]

    # -- Scalar summary outputs (for dashboard registry) --

    @property
    def nearest_support(self) -> float:
        below = self.levels_below(self._current_price)
        if not below:
            return float("nan")
        return max(below, key=lambda lvl: lvl.price).price

    @property
    def nearest_resistance(self) -> float:
        above = self.levels_above(self._current_price)
        if not above:
            return float("nan")
        return min(above, key=lambda lvl: lvl.price).price

    @property
    def strongest_support(self) -> float:
        below = self.levels_below(self._current_price)
        return below[0].price if below else float("nan")

    @property
    def strongest_resistance(self) -> float:
        above = self.levels_above(self._current_price)
        return above[0].price if above else float("nan")

    @property
    def level_count(self) -> float:
        return float(len(self._levels))

    def _reset(self) -> None:
        for detector in self._detectors:
            detector.reset()
        self._levels = []
        self._current_price = 0.0
        self._bar_count = 0
