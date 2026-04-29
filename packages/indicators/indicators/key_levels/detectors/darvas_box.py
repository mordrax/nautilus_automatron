"""DarvasBoxDetector — Darvas box breakout levels.

When price makes a new N-period high, wait for confirmation_bars without
exceeding that high to confirm a box top. The lowest low during the
consolidation period becomes the box bottom.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, DarvasBoxMeta


@dataclass
class _DarvasBox:
    box_top: float
    box_bottom: float
    confirmed: bool
    bars_in_box: int
    ts: int


@dataclass
class _PendingBox:
    """A box that is waiting for confirmation."""
    candidate_top: float
    bars_since_top: int
    lowest_low: float
    ts: int


class DarvasBoxDetector:

    def __init__(
        self,
        lookback_period: int = 20,
        confirmation_bars: int = 3,
        max_boxes: int = 10,
    ) -> None:
        self._lookback_period = lookback_period
        self._confirmation_bars = confirmation_bars
        self._max_boxes = max_boxes

        self._highs: deque[float] = deque(maxlen=lookback_period)
        self._bar_count = 0
        self._boxes: list[_DarvasBox] = []
        self._pending: _PendingBox | None = None

    @property
    def name(self) -> str:
        return "darvas_box"

    @property
    def warmup_bars(self) -> int:
        return self._lookback_period

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        ts = bar.ts_event

        self._highs.append(high)
        self._bar_count += 1

        if self._bar_count < self._lookback_period:
            return

        # Check if this bar makes a new N-period high
        period_high = max(self._highs)
        is_new_high = high == period_high and all(
            h <= high for h in list(self._highs)[:-1]
        )

        if self._pending is not None:
            if high > self._pending.candidate_top:
                # Exceeded the candidate top — restart with new high
                self._pending = _PendingBox(
                    candidate_top=high,
                    bars_since_top=0,
                    lowest_low=low,
                    ts=ts,
                )
            else:
                self._pending.bars_since_top += 1
                self._pending.lowest_low = min(self._pending.lowest_low, low)

                if self._pending.bars_since_top >= self._confirmation_bars:
                    # Confirmed!
                    self._boxes.append(_DarvasBox(
                        box_top=self._pending.candidate_top,
                        box_bottom=self._pending.lowest_low,
                        confirmed=True,
                        bars_in_box=self._pending.bars_since_top,
                        ts=self._pending.ts,
                    ))
                    if len(self._boxes) > self._max_boxes:
                        self._boxes.pop(0)
                    self._pending = None
        elif is_new_high:
            self._pending = _PendingBox(
                candidate_top=high,
                bars_since_top=0,
                lowest_low=low,
                ts=ts,
            )

    def levels(self) -> list[KeyLevel]:
        result: list[KeyLevel] = []
        for box in self._boxes:
            strength = min(1.0, max(0.0, box.bars_in_box / self._lookback_period))

            # Box top level
            result.append(KeyLevel(
                price=box.box_top,
                strength=strength,
                bounce_count=1,
                first_seen_ts=box.ts,
                last_touched_ts=box.ts,
                zone_upper=box.box_top,
                zone_lower=box.box_bottom,
                source="darvas_box",
                meta=DarvasBoxMeta(
                    box_top=box.box_top,
                    box_bottom=box.box_bottom,
                    confirmed=box.confirmed,
                    bars_in_box=box.bars_in_box,
                ),
            ))

            # Box bottom level
            result.append(KeyLevel(
                price=box.box_bottom,
                strength=strength,
                bounce_count=1,
                first_seen_ts=box.ts,
                last_touched_ts=box.ts,
                zone_upper=box.box_top,
                zone_lower=box.box_bottom,
                source="darvas_box",
                meta=DarvasBoxMeta(
                    box_top=box.box_top,
                    box_bottom=box.box_bottom,
                    confirmed=box.confirmed,
                    bars_in_box=box.bars_in_box,
                ),
            ))

        return result

    def reset(self) -> None:
        self._highs.clear()
        self._bar_count = 0
        self._boxes.clear()
        self._pending = None
