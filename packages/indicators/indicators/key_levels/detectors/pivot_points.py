"""PivotPointDetector — STUB.

Original snapshot-based implementation was removed in the KeyLevel event-model
slice (#118) because it constructs `KeyLevel` with the old `first_seen_ts` /
`last_touched_ts` shape.

# TODO(card #120): migrate to event-based KeyLevel — pivots become a fresh
# set of levels each session, with `start_ts` at session open and `end_ts` at
# session close.

This stub keeps the import surface stable. It produces no levels.
"""

from __future__ import annotations

from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel

PivotVariant = Literal["standard", "fibonacci", "camarilla", "woodie", "demark"]


class PivotPointDetector:

    def __init__(
        self,
        variant: PivotVariant = "standard",
        period_bars: int = 24,
    ) -> None:
        self._variant: PivotVariant = variant
        self._period_bars = period_bars

    @property
    def name(self) -> str:
        return f"pivot_{self._variant}"

    @property
    def warmup_bars(self) -> int:
        return self._period_bars

    def update(self, bar: Bar) -> None:
        return None

    def levels(self) -> list[KeyLevel]:
        return []

    def reset(self) -> None:
        return None
