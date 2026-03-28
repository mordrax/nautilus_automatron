"""MaConfluenceDetector — detect key levels where multiple EMAs converge.

When N or more exponential moving averages cluster within a tight band
(spread < threshold * ATR), the confluence zone acts as support/resistance.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, MaConfluenceMeta
from indicators.key_levels.shared.atr import StreamingAtr


class MaConfluenceDetector:

    def __init__(
        self,
        ma_periods: tuple[int, ...] = (9, 21, 50, 100, 200),
        min_converging: int = 3,
        spread_threshold: float = 0.5,
        atr_period: int = 14,
    ) -> None:
        self._ma_periods = ma_periods
        self._min_converging = min_converging
        self._spread_threshold = spread_threshold

        self._atr = StreamingAtr(period=atr_period)

        # EMA state: one value per period, None until initialized
        self._alphas = tuple(2.0 / (p + 1) for p in ma_periods)
        self._ema_values: list[float | None] = [None] * len(ma_periods)
        self._bar_count = 0

        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "ma_confluence"

    @property
    def warmup_bars(self) -> int:
        return max(self._ma_periods)

    def update(self, bar: Bar) -> None:
        close = float(bar.close)
        high = float(bar.high)
        low = float(bar.low)
        ts = bar.ts_event

        self._atr.update(high, low, close)
        self._bar_count += 1

        # Update each EMA
        for i, period in enumerate(self._ma_periods):
            if self._ema_values[i] is None:
                if self._bar_count >= period:
                    # Initialize: seed EMA with close (after enough bars)
                    self._ema_values[i] = close
                # Before enough bars, accumulate nothing (EMA starts at first eligible bar)
            else:
                alpha = self._alphas[i]
                self._ema_values[i] = close * alpha + self._ema_values[i] * (1 - alpha)

        # Check confluence only when all EMAs initialized and ATR ready
        if not self._atr.ready or any(v is None for v in self._ema_values):
            self._levels = []
            return

        self._rebuild_levels(close, ts)

    def _rebuild_levels(self, price: float, ts: int) -> None:
        atr = self._atr.value
        if atr <= 0:
            self._levels = []
            return

        ema_values = [v for v in self._ema_values if v is not None]
        max_spread = self._spread_threshold * atr

        # Sort EMAs with their period indices for tracking
        indexed = sorted(
            zip(ema_values, self._ma_periods),
            key=lambda x: x[0],
        )
        sorted_vals = [v for v, _ in indexed]
        sorted_periods = [p for _, p in indexed]

        # Find largest consecutive subset where max - min < threshold
        best_start = 0
        best_len = 0

        for start in range(len(sorted_vals)):
            for end in range(start + self._min_converging, len(sorted_vals) + 1):
                spread = sorted_vals[end - 1] - sorted_vals[start]
                if spread < max_spread:
                    if end - start > best_len:
                        best_start = start
                        best_len = end - start
                else:
                    break  # larger windows will only be wider

        if best_len < self._min_converging:
            self._levels = []
            return

        converging_vals = sorted_vals[best_start : best_start + best_len]
        converging_periods = tuple(
            sorted(sorted_periods[best_start : best_start + best_len])
        )

        zone_min = min(converging_vals)
        zone_max = max(converging_vals)
        level_price = sum(converging_vals) / len(converging_vals)
        spread = zone_max - zone_min

        # Strength: (count / total) * (1 / (1 + spread/atr)), capped at 1.0
        strength = (best_len / len(self._ma_periods)) * (
            1.0 / (1.0 + spread / atr)
        )
        strength = min(1.0, max(0.0, strength))

        spread_percent = (spread / price * 100.0) if price > 0 else 0.0

        self._levels = [
            KeyLevel(
                price=level_price,
                strength=strength,
                bounce_count=0,
                first_seen_ts=ts,
                last_touched_ts=ts,
                zone_upper=zone_max,
                zone_lower=zone_min,
                source="ma_confluence",
                meta=MaConfluenceMeta(
                    converging_periods=converging_periods,
                    spread_percent=spread_percent,
                ),
            )
        ]

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._ema_values = [None] * len(self._ma_periods)
        self._bar_count = 0
        self._levels = []
