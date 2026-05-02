"""OrderBlockDetector — last opposite-direction candle before a strong move
(lifecycle-tracked).

A bullish order block is the last bearish candle before a strong bullish
displacement (body > displacement_threshold * ATR). A bearish order block is
the last bullish candle before a strong bearish displacement.

Each block is born at the OB candle close (the displacement bar's ts).
A block lives until either:

- it is fully mitigated — price re-enters the OB and exits beyond the
  opposite zone edge (mitigation_pct >= 1.0)
- it ages out (no touch for `max_idle_bars` bars relative to the bar
  interval — same convention as other detectors)

The single `price` is the centroid (midpoint) of the OB candle's body;
``zone_upper`` / ``zone_lower`` are the body extremes.

`bounce_count` increments when the bar overlaps the zone band; `touch_count`
mirrors `bounce_count` for the unified meta API.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, OrderBlockMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedOrderBlock:
    id: int
    block_side: Literal["bullish", "bearish"]
    centroid: float
    zone_upper: float
    zone_lower: float
    block_open: float
    block_close: float
    displacement_atr_multiple: float
    start_ts: int
    end_ts: int | None
    last_touch_ts: int
    touch_count: int
    deepest_penetration: float
    side: Literal["high", "low"]


class OrderBlockDetector:

    def __init__(
        self,
        atr_period: int = 14,
        displacement_threshold: float = 2.0,
        max_idle_bars: int = 200,
        lookback_bars: int = 10,
    ) -> None:
        self._atr_period = atr_period
        self._displacement_threshold = displacement_threshold
        self._max_idle_bars = max_idle_bars
        self._lookback_bars = lookback_bars

        self._atr = StreamingAtr(period=atr_period)
        self._recent_bars: deque[Bar] = deque(maxlen=lookback_bars)

        self._tracked: list[_TrackedOrderBlock] = []
        self._next_id: int = 0
        self._last_bar_ts: int | None = None
        self._bar_interval_ns: int | None = None

    @property
    def name(self) -> str:
        return "order_block"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period + 1

    # ------------------------------------------------------------------ update

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        open_ = float(bar.open)
        ts = bar.ts_event

        if self._last_bar_ts is not None and self._bar_interval_ns is None:
            delta = ts - self._last_bar_ts
            if delta > 0:
                self._bar_interval_ns = delta
        self._last_bar_ts = ts

        self._atr.update(high, low, close)

        # Per-bar lifecycle on existing blocks.
        for ob in self._tracked:
            if ob.end_ts is not None:
                continue
            self._apply_bar_to_block(ob, high, low, close, ts)

        # Detect new order blocks on this bar.
        if self._atr.ready and len(self._recent_bars) >= 1:
            body = abs(close - open_)
            atr_val = self._atr.value
            if atr_val > 0 and body > self._displacement_threshold * atr_val:
                displacement_multiple = body / atr_val
                is_bullish_move = close > open_
                self._emit_for_displacement(
                    is_bullish_move=is_bullish_move,
                    displacement_multiple=displacement_multiple,
                    current_close=close,
                    ts=ts,
                )

        self._recent_bars.append(bar)

    def _emit_for_displacement(
        self,
        is_bullish_move: bool,
        displacement_multiple: float,
        current_close: float,
        ts: int,
    ) -> None:
        for prev_bar in reversed(self._recent_bars):
            prev_open = float(prev_bar.open)
            prev_close = float(prev_bar.close)
            prev_is_bearish = prev_close < prev_open
            prev_is_bullish = prev_close > prev_open

            if is_bullish_move and prev_is_bearish:
                self._emit_block(
                    block_side="bullish",
                    prev_open=prev_open,
                    prev_close=prev_close,
                    displacement_multiple=displacement_multiple,
                    ts=ts,
                    current_close=current_close,
                )
                return
            if (not is_bullish_move) and prev_is_bullish:
                self._emit_block(
                    block_side="bearish",
                    prev_open=prev_open,
                    prev_close=prev_close,
                    displacement_multiple=displacement_multiple,
                    ts=ts,
                    current_close=current_close,
                )
                return

    def _emit_block(
        self,
        block_side: Literal["bullish", "bearish"],
        prev_open: float,
        prev_close: float,
        displacement_multiple: float,
        ts: int,
        current_close: float,
    ) -> None:
        zone_upper = max(prev_open, prev_close)
        zone_lower = min(prev_open, prev_close)
        centroid = (zone_upper + zone_lower) / 2.0
        # Bullish OB acts as support (below price → side="low"); bearish OB
        # acts as resistance (above price → side="high"). Spec mandates the
        # mapping by block direction, not relative price position.
        side: Literal["high", "low"] = "low" if block_side == "bullish" else "high"

        self._tracked.append(_TrackedOrderBlock(
            id=self._next_id,
            block_side=block_side,
            centroid=centroid,
            zone_upper=zone_upper,
            zone_lower=zone_lower,
            block_open=prev_open,
            block_close=prev_close,
            displacement_atr_multiple=displacement_multiple,
            start_ts=ts,
            end_ts=None,
            last_touch_ts=ts,
            touch_count=0,
            deepest_penetration=0.0,
            side=side,
        ))
        self._next_id += 1

    def _apply_bar_to_block(
        self,
        ob: _TrackedOrderBlock,
        high: float,
        low: float,
        close: float,
        ts: int,
    ) -> None:
        zone_size = ob.zone_upper - ob.zone_lower

        # Touch: bar overlaps zone band.
        if low <= ob.zone_upper and high >= ob.zone_lower:
            ob.touch_count += 1
            ob.last_touch_ts = ts

            # Track penetration depth.
            if ob.block_side == "bullish":
                # Bullish OB: price dipping into / through it from above.
                # Penetration = how far below zone_upper price went (capped at
                # zone size for full mitigation when price exits below).
                penetration = max(0.0, ob.zone_upper - max(low, ob.zone_lower - zone_size))
            else:
                # Bearish OB: price pushing up into it from below.
                penetration = max(0.0, min(high, ob.zone_upper + zone_size) - ob.zone_lower)
            ob.deepest_penetration = max(ob.deepest_penetration, penetration)

        # Mitigation: full mitigation when close exits the opposite side after
        # entering. We approximate by checking the bar fully traversed the
        # zone (bullish OB: close < zone_lower after a touch; bearish OB:
        # close > zone_upper after a touch).
        if ob.touch_count > 0:
            if ob.block_side == "bullish" and close < ob.zone_lower:
                ob.deepest_penetration = max(ob.deepest_penetration, zone_size)
                ob.end_ts = ts
                return
            if ob.block_side == "bearish" and close > ob.zone_upper:
                ob.deepest_penetration = max(ob.deepest_penetration, zone_size)
                ob.end_ts = ts
                return

        # Aged-out check.
        bar_interval = self._bar_interval_ns or 1
        idle_ns = self._max_idle_bars * bar_interval
        if ts - ob.last_touch_ts > idle_ns:
            ob.end_ts = ob.last_touch_ts

    # ------------------------------------------------------------------ levels

    def levels(self) -> list[KeyLevel]:
        out: list[KeyLevel] = []
        for ob in self._tracked:
            zone_size = ob.zone_upper - ob.zone_lower
            mitigation_pct = (
                ob.deepest_penetration / zone_size if zone_size > 0 else 0.0
            )
            mitigation_pct = max(0.0, min(1.0, mitigation_pct))

            # Strength: scaled by displacement and decayed by mitigation.
            base = min(1.0, ob.displacement_atr_multiple / 10.0)
            strength = max(0.0, min(1.0, base * (1.0 - mitigation_pct)))

            out.append(KeyLevel(
                price=ob.centroid,
                strength=strength,
                start_ts=ob.start_ts,
                end_ts=ob.end_ts,
                source="order_block",
                bounce_count=max(1, ob.touch_count),
                zone_upper=ob.zone_upper,
                zone_lower=ob.zone_lower,
                meta=OrderBlockMeta(
                    block_side=ob.block_side,
                    displacement_atr_multiple=ob.displacement_atr_multiple,
                    block_open=ob.block_open,
                    block_close=ob.block_close,
                    mitigation_pct=mitigation_pct,
                    side=ob.side,
                    touch_count=ob.touch_count,
                ),
            ))
        return out

    def reset(self) -> None:
        self._atr.reset()
        self._recent_bars.clear()
        self._tracked.clear()
        self._next_id = 0
        self._last_bar_ts = None
        self._bar_interval_ns = None
