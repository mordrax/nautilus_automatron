"""WickRejectionDetector — STUB.

Original snapshot-based implementation was removed in the KeyLevel event-model
slice (#118) because it constructs `KeyLevel` with the old `first_seen_ts` /
`last_touched_ts` shape.

# TODO(card #119): migrate to event-based KeyLevel — track each rejection
# cluster as a `_TrackedLevel` with start_ts/end_ts lifecycle.

This stub keeps the import surface stable so the package still imports cleanly
and the server can boot. It produces no levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel


class WickRejectionDetector:

    def __init__(
        self,
        min_wick_ratio: float = 2.0,
        zone_atr_multiple: float = 1.0,
        atr_period: int = 14,
        min_rejections: int = 2,
        max_rejections: int = 200,
    ) -> None:
        # Args preserved so existing callers don't break on TypeError.
        self._min_wick_ratio = min_wick_ratio
        self._zone_atr_multiple = zone_atr_multiple
        self._atr_period = atr_period
        self._min_rejections = min_rejections
        self._max_rejections = max_rejections

    @property
    def name(self) -> str:
        return "wick_rejection"

    @property
    def warmup_bars(self) -> int:
        return 1

    def update(self, bar: Bar) -> None:
        return None

    def levels(self) -> list[KeyLevel]:
        return []

    def reset(self) -> None:
        return None
