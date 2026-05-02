"""PsychologicalLevelDetector — STUB.

Original snapshot-based implementation was removed in the KeyLevel event-model
slice (#118) because it constructs `KeyLevel` with the old `first_seen_ts` /
`last_touched_ts` shape.

# TODO(card #120): migrate to event-based KeyLevel — psychological levels are
# inherently long-lived horizontals; lifecycle ends only when price has moved
# far enough that the level is out of relevant range.

This stub keeps the import surface stable. It produces no levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel


class PsychologicalLevelDetector:

    def __init__(
        self,
        tier_steps: dict[str, float],
        range_levels: int = 5,
        atr_period: int = 14,
        lookback: int = 200,
    ) -> None:
        self._tier_steps = tier_steps
        self._range_levels = range_levels
        self._atr_period = atr_period
        self._lookback = lookback

    @property
    def name(self) -> str:
        return "psychological"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period

    def update(self, bar: Bar) -> None:
        return None

    def levels(self) -> list[KeyLevel]:
        return []

    def reset(self) -> None:
        return None
