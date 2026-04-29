"""AnchoredVwapDetector -- VWAP anchored to swing highs and lows.

Each confirmed swing point becomes an anchor. From each anchor, a running
VWAP is computed as cumulative(typical_price * volume) / cumulative(volume).
The most recent value of each anchor's VWAP is emitted as a dynamic level.
"""

from __future__ import annotations

from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import AnchoredVwapMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.swing import SwingDetector


class _AnchorState:
    """Running VWAP state from a single anchor point."""

    __slots__ = ("anchor_ts", "anchor_type", "cum_pv", "cum_vol", "vwap")

    def __init__(self, anchor_ts: int, anchor_type: Literal["swing_high", "swing_low"]) -> None:
        self.anchor_ts = anchor_ts
        self.anchor_type = anchor_type
        self.cum_pv: float = 0.0
        self.cum_vol: float = 0.0
        self.vwap: float = 0.0

    def update(self, typical_price: float, volume: float) -> None:
        self.cum_pv += typical_price * volume
        self.cum_vol += volume
        if self.cum_vol > 0:
            self.vwap = self.cum_pv / self.cum_vol


class AnchoredVwapDetector:

    def __init__(
        self,
        swing_period: int = 5,
        max_anchors: int = 5,
        atr_period: int = 14,
    ) -> None:
        self._swing_period = swing_period
        self._max_anchors = max_anchors
        self._atr = StreamingAtr(period=atr_period)
        self._swing_detector = SwingDetector(period=swing_period)

        self._bar_index: int = 0
        self._anchors: list[_AnchorState] = []
        self._levels: list[KeyLevel] = []
        self._last_ts: int = 0

    @property
    def name(self) -> str:
        return "anchored_vwap"

    @property
    def warmup_bars(self) -> int:
        return self._swing_detector.warmup_bars

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        volume = float(bar.volume)
        ts = bar.ts_event

        self._atr.update(high, low, close)
        self._last_ts = ts

        typical_price = (high + low + close) / 3.0

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )
        if swing is not None:
            anchor_type: Literal["swing_high", "swing_low"] = (
                "swing_high" if swing.side == "high" else "swing_low"
            )
            self._anchors.append(_AnchorState(anchor_ts=swing.ts, anchor_type=anchor_type))
            if len(self._anchors) > self._max_anchors:
                self._anchors.pop(0)

        # Update all active anchors with current bar
        for anchor in self._anchors:
            anchor.update(typical_price, volume)

        self._bar_index += 1

        if self._atr.ready and self._anchors:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        atr = self._atr.value
        levels: list[KeyLevel] = []

        for anchor in self._anchors:
            if anchor.cum_vol <= 0:
                continue

            vwap = anchor.vwap
            levels.append(KeyLevel(
                price=vwap,
                strength=min(1.0, anchor.cum_vol / 10000.0),
                bounce_count=1,
                first_seen_ts=anchor.anchor_ts,
                last_touched_ts=self._last_ts,
                zone_upper=vwap + atr * 0.25,
                zone_lower=vwap - atr * 0.25,
                source="anchored_vwap",
                meta=AnchoredVwapMeta(
                    anchor_ts=anchor.anchor_ts,
                    anchor_type=anchor.anchor_type,
                    cumulative_volume=anchor.cum_vol,
                ),
            ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._swing_detector.reset()
        self._bar_index = 0
        self._anchors.clear()
        self._levels = []
        self._last_ts = 0
