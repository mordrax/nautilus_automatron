"""OrderBlockDetector — find the last opposing candle before an impulsive move.

An order block is the candle range where institutional orders were placed,
identified by the last opposing candle before a displacement (impulsive move
exceeding an ATR-multiple threshold).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, OrderBlockMeta
from indicators.key_levels.shared.atr import StreamingAtr


@dataclass
class _TrackedOrderBlock:
    price: float
    zone_upper: float
    zone_lower: float
    side: str  # "bullish" | "bearish"
    displacement_atr_multiple: float
    block_open: float
    block_close: float
    ts: int
    age: int


class OrderBlockDetector:

    def __init__(
        self,
        atr_period: int = 14,
        displacement_threshold: float = 2.0,
        max_age_bars: int = 200,
    ) -> None:
        self._atr_period = atr_period
        self._displacement_threshold = displacement_threshold
        self._max_age_bars = max_age_bars

        self._atr = StreamingAtr(period=atr_period)
        self._recent_bars: deque[Bar] = deque(maxlen=10)
        self._tracked: list[_TrackedOrderBlock] = []

    @property
    def name(self) -> str:
        return "order_block"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        open_ = float(bar.open)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        # Age existing blocks and expire old ones
        for ob in self._tracked:
            ob.age += 1
        self._tracked = [ob for ob in self._tracked if ob.age < self._max_age_bars]

        if self._atr.ready and len(self._recent_bars) >= 2:
            body = abs(close - open_)
            atr_val = self._atr.value
            if atr_val > 0 and body > self._displacement_threshold * atr_val:
                displacement_multiple = body / atr_val
                is_bullish_move = close > open_

                # Look back for the last opposing candle
                for prev_bar in reversed(self._recent_bars):
                    prev_open = float(prev_bar.open)
                    prev_close = float(prev_bar.close)
                    prev_is_bearish = prev_close < prev_open
                    prev_is_bullish = prev_close > prev_open

                    if is_bullish_move and prev_is_bearish:
                        # Bullish OB: bearish candle before bullish move
                        block_upper = max(prev_open, prev_close)
                        block_lower = min(prev_open, prev_close)
                        midpoint = (block_upper + block_lower) / 2.0
                        self._tracked.append(_TrackedOrderBlock(
                            price=midpoint,
                            zone_upper=block_upper,
                            zone_lower=block_lower,
                            side="bullish",
                            displacement_atr_multiple=displacement_multiple,
                            block_open=prev_open,
                            block_close=prev_close,
                            ts=prev_bar.ts_event,
                            age=0,
                        ))
                        break
                    elif not is_bullish_move and prev_is_bullish:
                        # Bearish OB: bullish candle before bearish move
                        block_upper = max(prev_open, prev_close)
                        block_lower = min(prev_open, prev_close)
                        midpoint = (block_upper + block_lower) / 2.0
                        self._tracked.append(_TrackedOrderBlock(
                            price=midpoint,
                            zone_upper=block_upper,
                            zone_lower=block_lower,
                            side="bearish",
                            displacement_atr_multiple=displacement_multiple,
                            block_open=prev_open,
                            block_close=prev_close,
                            ts=prev_bar.ts_event,
                            age=0,
                        ))
                        break

        self._recent_bars.append(bar)

    def levels(self) -> list[KeyLevel]:
        result: list[KeyLevel] = []
        for ob in self._tracked:
            decay = 1.0 - ob.age / self._max_age_bars
            strength = min(1.0, max(0.0, ob.displacement_atr_multiple * decay / 10.0))
            result.append(KeyLevel(
                price=ob.price,
                strength=strength,
                bounce_count=1,
                first_seen_ts=ob.ts,
                last_touched_ts=ob.ts,
                zone_upper=ob.zone_upper,
                zone_lower=ob.zone_lower,
                source="order_block",
                meta=OrderBlockMeta(
                    side=ob.side,
                    displacement_atr_multiple=ob.displacement_atr_multiple,
                    block_open=ob.block_open,
                    block_close=ob.block_close,
                ),
            ))
        return result

    def reset(self) -> None:
        self._atr.reset()
        self._recent_bars.clear()
        self._tracked.clear()
