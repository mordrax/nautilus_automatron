"""DarvasBoxDetector — confirmed top + bottom boxes (lifecycle-tracked).

When price makes a new ``lookback_period``-bar high, wait for
``confirmation_bars`` bars without exceeding that high to confirm a box
top. The lowest low during the consolidation period becomes the box bottom.

Each confirmed box is a single zoned level (``zone_upper`` = box top,
``zone_lower`` = box bottom, ``price`` = midpoint). The level lives until a
sustained close beyond the box by ``break_atr_multiple * ATR`` (breakout)
or ages out.

``side`` is computed at emit time relative to the current close: "high" if
the box is above price, else "low".
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import DarvasBoxMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _DarvasBox:
    id: int
    box_top: float
    box_bottom: float
    centroid: float
    confirmed: bool
    bars_in_box: int
    start_ts: int
    end_ts: int | None
    last_touch_ts: int
    touch_count: int
    bars_through: int
    side: Literal["high", "low"]


@dataclass
class _PendingBox:
    candidate_top: float
    bars_since_top: int
    lowest_low: float
    ts: int


class DarvasBoxDetector:

    def __init__(
        self,
        lookback_period: int = 20,
        confirmation_bars: int = 3,
        atr_period: int = 14,
        break_atr_multiple: float = 1.0,
        max_idle_bars: int = 200,
    ) -> None:
        self._lookback_period = lookback_period
        self._confirmation_bars = confirmation_bars
        self._atr_period = atr_period
        self._break_atr_multiple = break_atr_multiple
        self._max_idle_bars = max_idle_bars

        self._atr = StreamingAtr(period=atr_period)
        self._highs: deque[float] = deque(maxlen=lookback_period)
        self._bar_count = 0

        self._tracked: list[_DarvasBox] = []
        self._pending: _PendingBox | None = None
        self._next_id: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

    @property
    def name(self) -> str:
        return "darvas_box"

    @property
    def warmup_bars(self) -> int:
        return self._lookback_period

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)

        # Per-bar lifecycle on existing confirmed boxes.
        for box in self._tracked:
            if box.end_ts is not None:
                continue
            self._apply_bar_to_box(box, high, low, close, ts)

        self._highs.append(high)
        self._bar_count += 1

        if self._bar_count < self._lookback_period:
            return

        period_high = max(self._highs)
        is_new_high = high == period_high and all(
            h <= high for h in list(self._highs)[:-1]
        )

        if self._pending is not None:
            if high > self._pending.candidate_top:
                # Exceeded — restart with new candidate.
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
                    self._emit_box(close=close, ts=ts)
                    self._pending = None
        elif is_new_high:
            self._pending = _PendingBox(
                candidate_top=high,
                bars_since_top=0,
                lowest_low=low,
                ts=ts,
            )

    def _emit_box(self, close: float, ts: int) -> None:
        assert self._pending is not None
        box_top = self._pending.candidate_top
        box_bottom = self._pending.lowest_low
        centroid = (box_top + box_bottom) / 2.0
        # side relative to current close.
        side: Literal["high", "low"] = "high" if centroid > close else "low"

        self._tracked.append(_DarvasBox(
            id=self._next_id,
            box_top=box_top,
            box_bottom=box_bottom,
            centroid=centroid,
            confirmed=True,
            bars_in_box=self._pending.bars_since_top,
            start_ts=self._pending.ts,
            end_ts=None,
            last_touch_ts=ts,
            touch_count=0,
            bars_through=0,
            side=side,
        ))
        self._next_id += 1

    def _apply_bar_to_box(
        self,
        box: _DarvasBox,
        high: float,
        low: float,
        close: float,
        ts: int,
    ) -> None:
        atr_value = self._atr.value if self._atr.ready else 0.0

        # Breakout check — close beyond the box by break_atr_multiple * ATR.
        if atr_value > 0:
            beyond = (
                close > box.box_top + self._break_atr_multiple * atr_value
                or close < box.box_bottom - self._break_atr_multiple * atr_value
            )
            if beyond:
                box.end_ts = ts
                return

        # Touch: bar overlaps the box zone.
        if low <= box.box_top and high >= box.box_bottom:
            box.touch_count += 1
            box.last_touch_ts = ts

        # Aged-out.
        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - box.last_touch_ts > idle_ns:
            box.end_ts = box.last_touch_ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for box in self._tracked:
            strength = max(
                0.0, min(1.0, box.bars_in_box / self._lookback_period),
            )
            out.append(KeyLevel(
                price=box.centroid,
                strength=strength,
                start_ts=box.start_ts,
                end_ts=box.end_ts,
                source="darvas_box",
                bounce_count=max(1, box.touch_count),
                zone_upper=box.box_top,
                zone_lower=box.box_bottom,
                meta=DarvasBoxMeta(
                    box_top=box.box_top,
                    box_bottom=box.box_bottom,
                    confirmed=box.confirmed,
                    bars_in_box=box.bars_in_box,
                    side=box.side,
                    touch_count=box.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._highs.clear()
        self._bar_count = 0
        self._tracked.clear()
        self._pending = None
        self._next_id = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
