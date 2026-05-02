"""PsychologicalLevelDetector -- detect key levels at round numbers.

Generates levels at psychologically significant round numbers relative to
current price.  Tier definitions are instrument-dependent:

    XAUUSD: {"major": 100.0, "minor": 50.0, "micro": 25.0}
    EURUSD: {"major": 0.01, "minor": 0.005, "micro": 0.0025}

Strength is tier-based (major > minor > micro) and boosted when price has
historically bounced at the level.
"""

from __future__ import annotations

import math

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, PsychologicalMeta
from indicators.key_levels.shared.atr import StreamingAtr

_TIER_BASE_STRENGTH: dict[str, float] = {
    "major": 0.7,
    "minor": 0.4,
    "micro": 0.2,
}

_BOUNCE_BONUS = 0.1
_MAX_BOUNCE_BONUS = 0.3


class PsychologicalLevelDetector:
    """Detects key levels at psychologically significant round numbers.

    Args:
        tier_steps: Dict mapping tier name to price step size.
                    Example: {"major": 100.0, "minor": 50.0, "micro": 25.0}
        range_levels: How many levels above/below current price to generate per tier.
        atr_period: ATR period for zone width calculation.
        lookback: Bars to track for bounce counting at each level.
    """

    def __init__(
        self,
        tier_steps: dict[str, float],
        range_levels: int = 5,
        atr_period: int = 14,
        lookback: int = 200,
    ) -> None:
        self._tier_steps = tier_steps
        self._range_levels = range_levels
        self._lookback = lookback

        self._atr = StreamingAtr(period=atr_period)

        # Bounce tracking: level_key -> bounce count
        # level_key is (tier, round_value)
        self._bounce_counts: dict[tuple[str, float], int] = {}

        # Track whether price is currently inside a level's zone
        self._in_zone: dict[tuple[str, float], bool] = {}

        # Current bar's close price
        self._last_close: float | None = None
        self._last_ts: int = 0

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "psychological"

    @property
    def warmup_bars(self) -> int:
        return 0

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)
        self._last_close = close
        self._last_ts = ts

        # Update bounce tracking
        self._update_bounces(high, low, close)

        # Rebuild levels around current price
        self._rebuild_levels(close, ts)

    def _zone_width(self) -> float:
        """Half-width of the zone around a level."""
        if self._atr.ready:
            return self._atr.value * 0.25
        return 0.0

    def _update_bounces(self, high: float, low: float, close: float) -> None:
        """Track bounces: price enters then exits a level's zone."""
        zone_hw = self._zone_width()
        if zone_hw <= 0:
            return

        # Check all tiers and generate levels around current close
        for tier_name, step in self._tier_steps.items():
            base = math.floor(close / step) * step
            for i in range(-self._range_levels, self._range_levels + 1):
                level_price = base + i * step
                key = (tier_name, level_price)

                price_in_zone = (low <= level_price + zone_hw) and (
                    high >= level_price - zone_hw
                )

                was_in_zone = self._in_zone.get(key, False)

                if price_in_zone and not was_in_zone:
                    # Entered zone
                    self._in_zone[key] = True
                elif not price_in_zone and was_in_zone:
                    # Exited zone -- count as bounce
                    self._in_zone[key] = False
                    self._bounce_counts[key] = self._bounce_counts.get(key, 0) + 1

    def _rebuild_levels(self, price: float, ts: int) -> None:
        levels: list[KeyLevel] = []
        zone_hw = self._zone_width()

        for tier_name, step in self._tier_steps.items():
            base = math.floor(price / step) * step
            base_strength = _TIER_BASE_STRENGTH.get(tier_name, 0.2)

            for i in range(-self._range_levels, self._range_levels + 1):
                level_price = base + i * step
                key = (tier_name, level_price)
                bounces = self._bounce_counts.get(key, 0)

                bounce_bonus = min(bounces * _BOUNCE_BONUS, _MAX_BOUNCE_BONUS)
                strength = min(1.0, base_strength + bounce_bonus)

                levels.append(
                    KeyLevel(
                        price=level_price,
                        strength=strength,
                        bounce_count=bounces,
                        first_seen_ts=ts,
                        last_touched_ts=ts,
                        zone_upper=level_price + zone_hw,
                        zone_lower=level_price - zone_hw,
                        source="psychological",
                        meta=PsychologicalMeta(
                            tier=tier_name,
                            round_value=level_price,
                        ),
                    )
                )

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._bounce_counts.clear()
        self._in_zone.clear()
        self._last_close = None
        self._last_ts = 0
        self._levels = []
