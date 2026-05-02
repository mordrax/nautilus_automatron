"""AtrVolatilityDetector — STUB.

Original snapshot-based implementation was removed in the KeyLevel event-model
slice (#118) because it constructs `KeyLevel` with the old `first_seen_ts` /
`last_touched_ts` shape.

# TODO(card #120): migrate to event-based KeyLevel — emit per-multiplier
# levels as short-lived events anchored at each bar.

This stub keeps the import surface stable. It produces no levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel


class AtrVolatilityDetector:

    def __init__(
        self,
        atr_period: int = 14,
        multipliers: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0),
    ) -> None:
        self._atr_period = atr_period
        self._multipliers = multipliers

    @property
    def name(self) -> str:
        return "atr_volatility"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period

    def update(self, bar: Bar) -> None:
        return None

    def levels(self) -> list[KeyLevel]:
        return []

    def reset(self) -> None:
        return None
