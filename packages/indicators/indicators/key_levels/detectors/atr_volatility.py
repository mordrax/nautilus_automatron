"""AtrVolatilityDetector — key levels at ATR multiples from current close.

Generates levels representing statistical expected range boundaries — how far
price can reasonably move based on recent volatility.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import AtrVolatilityMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr


class AtrVolatilityDetector:
    """Detects key levels at ATR multiples from current close.

    Args:
        atr_period: ATR calculation period. Default 14.
        multipliers: Tuple of ATR multiples. Default (1.0, 1.5, 2.0, 3.0).
    """

    def __init__(
        self,
        atr_period: int = 14,
        multipliers: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0),
    ) -> None:
        self._atr = StreamingAtr(period=atr_period)
        self._atr_period = atr_period
        self._multipliers = multipliers
        self._max_multiplier = max(multipliers)
        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "atr_volatility"

    @property
    def warmup_bars(self) -> int:
        return self._atr_period

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        if not self._atr.ready:
            self._levels = []
            return

        atr = self._atr.value
        zone_half = 0.25 * atr

        levels: list[KeyLevel] = []
        for mult in self._multipliers:
            strength = mult / self._max_multiplier

            resistance_price = close + mult * atr
            levels.append(KeyLevel(
                price=resistance_price,
                strength=strength,
                bounce_count=0,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=resistance_price + zone_half,
                zone_lower=resistance_price - zone_half,
                source="atr_volatility",
                meta=AtrVolatilityMeta(
                    atr_value=atr,
                    multiplier=mult,
                    anchor_price=close,
                ),
            ))

            support_price = close - mult * atr
            levels.append(KeyLevel(
                price=support_price,
                strength=strength,
                bounce_count=0,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=support_price + zone_half,
                zone_lower=support_price - zone_half,
                source="atr_volatility",
                meta=AtrVolatilityMeta(
                    atr_value=atr,
                    multiplier=mult,
                    anchor_price=close,
                ),
            ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._levels = []
