"""ZigZagIndicator — threshold-based reversal detection.

Identifies significant price reversals by filtering out moves below a
configurable threshold. Supports percentage-based and ATR-based modes.
"""

from __future__ import annotations

from collections import deque

from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.indicators.base import Indicator
from nautilus_trader.indicators.volatility import AverageTrueRange
from nautilus_trader.model.data import Bar

from indicators.zigzag.model import ZigZagPivot

_VALID_MODES = ("PERCENTAGE", "ATR")
_VALID_BASES = ("PIVOT", "TENTATIVE")


class ZigZagIndicator(Indicator):
    """A zigzag indicator that identifies significant price reversals.

    In PERCENTAGE mode, a reversal is confirmed when price moves by at least
    ``threshold`` (decimal ratio, e.g. 0.05 = 5%) from the last pivot.

    In ATR mode, a reversal is confirmed when price moves by at least
    ``threshold * ATR`` from the last pivot.

    Parameters
    ----------
    threshold : float
        Reversal threshold (> 0). Decimal ratio in PERCENTAGE mode,
        ATR multiplier in ATR mode.
    mode : str, default "PERCENTAGE"
        Threshold mode: "PERCENTAGE" or "ATR".
    atr_period : int, default 14
        ATR lookback period (ATR mode only).
    threshold_base : str, default "PIVOT"
        Base price for threshold: "PIVOT" or "TENTATIVE".
    max_pivots : int, default 10000
        Max confirmed pivots to retain. 0 = unlimited.
    """

    def __init__(
        self,
        threshold: float,
        mode: str = "PERCENTAGE",
        atr_period: int = 14,
        threshold_base: str = "PIVOT",
        max_pivots: int = 10000,
    ) -> None:
        PyCondition.positive(threshold, "threshold")
        PyCondition.is_in(mode, _VALID_MODES, "mode", str(_VALID_MODES))
        PyCondition.is_in(threshold_base, _VALID_BASES, "threshold_base", str(_VALID_BASES))
        PyCondition.positive_int(atr_period, "atr_period")
        PyCondition.not_negative_int(max_pivots, "max_pivots")

        super().__init__(params=[threshold, mode, atr_period, threshold_base, max_pivots])

        self.threshold = threshold
        self.atr_period = atr_period
        self.max_pivots = max_pivots
        self._mode = mode
        self._threshold_base = threshold_base

        self._atr: AverageTrueRange | None = (
            AverageTrueRange(atr_period) if mode == "ATR" else None
        )

        self._pivots: deque[ZigZagPivot] | list[ZigZagPivot] = (
            deque(maxlen=max_pivots) if max_pivots > 0 else []
        )

        self._bar_count: int = 0
        self._initial_high: float = 0.0
        self._initial_low: float = 0.0
        self._initial_high_ts: int = 0
        self._initial_low_ts: int = 0

        self.direction: int = 0
        self.changed: bool = False
        self.pivot_price: float = 0.0
        self.pivot_timestamp: int = 0
        self.pivot_direction: int = 0
        self.tentative_price: float = 0.0
        self.tentative_timestamp: int = 0
        self.pivot_count: int = 0

    @property
    def pivots(self) -> list[ZigZagPivot]:
        """Return a copy of confirmed pivots."""
        return list(self._pivots)

    def handle_bar(self, bar: Bar) -> None:
        """Update the indicator with the given bar."""
        PyCondition.not_none(bar, "bar")
        self._update(
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            ts_ns=bar.ts_init,
        )

    def _update(
        self,
        high: float,
        low: float,
        close: float,
        ts_ns: int,
    ) -> None:
        # Update ATR if in ATR mode
        if self._atr is not None:
            self._atr.update_raw(high, low, close)

        if not self.has_inputs:
            self._set_has_inputs(True)

        self.changed = False

        # --- Initialization phase ---
        if self.direction == 0:
            if self._bar_count == 0 or high > self._initial_high:
                self._initial_high = high
                self._initial_high_ts = ts_ns
            if self._bar_count == 0 or low < self._initial_low:
                self._initial_low = low
                self._initial_low_ts = ts_ns

            # ATR needs warmup
            if self._atr is not None and not self._atr.initialized:
                self._bar_count += 1
                return

            # Compute both reversal distances
            high_move = self._initial_high - low
            low_move = high - self._initial_low

            if self._mode == "PERCENTAGE":
                high_threshold = self._initial_high * self.threshold
                low_threshold = self._initial_low * self.threshold
            else:
                atr_threshold = self._atr.value * self.threshold  # type: ignore[union-attr]
                high_threshold = atr_threshold
                low_threshold = atr_threshold

            high_reversal = high_move >= high_threshold
            low_reversal = low_move >= low_threshold

            # If both qualify, pick the larger move
            if high_reversal and low_reversal:
                if high_move >= low_move:
                    low_reversal = False
                else:
                    high_reversal = False

            if high_reversal:
                self._confirm_initial_pivot(
                    self._initial_high, self._initial_high_ts, 1, low, ts_ns, -1,
                )
                self._bar_count += 1
                return

            if low_reversal:
                self._confirm_initial_pivot(
                    self._initial_low, self._initial_low_ts, -1, high, ts_ns, 1,
                )
                self._bar_count += 1
                return

            self._bar_count += 1
            return

        # --- Active tracking ---
        effective_threshold = self._compute_threshold()

        if self.direction == 1:
            if high > self.tentative_price:
                self.tentative_price = high
                self.tentative_timestamp = ts_ns
                if self._mode == "PERCENTAGE" and self._threshold_base == "TENTATIVE":
                    effective_threshold = self.tentative_price * self.threshold

            if low <= self.tentative_price - effective_threshold:
                self._confirm_pivot(1, low, ts_ns, -1)

        elif self.direction == -1:
            if low < self.tentative_price:
                self.tentative_price = low
                self.tentative_timestamp = ts_ns
                if self._mode == "PERCENTAGE" and self._threshold_base == "TENTATIVE":
                    effective_threshold = self.tentative_price * self.threshold

            if high >= self.tentative_price + effective_threshold:
                self._confirm_pivot(-1, high, ts_ns, 1)

        self._bar_count += 1

    def _compute_threshold(self) -> float:
        if self._mode == "PERCENTAGE":
            base = (
                self.pivot_price
                if self._threshold_base == "PIVOT"
                else self.tentative_price
            )
            return base * self.threshold
        return self._atr.value * self.threshold  # type: ignore[union-attr]

    def _confirm_initial_pivot(
        self,
        pivot_price: float,
        pivot_ts: int,
        pivot_dir: int,
        tentative_price: float,
        tentative_ts: int,
        new_direction: int,
    ) -> None:
        pivot = ZigZagPivot(
            price=pivot_price,
            timestamp=pivot_ts,
            direction=pivot_dir,
            bar_index=self._bar_count,
        )
        self._pivots.append(pivot)
        self.pivot_price = pivot_price
        self.pivot_timestamp = pivot_ts
        self.pivot_direction = pivot_dir
        self.pivot_count = 1
        self.direction = new_direction
        self.tentative_price = tentative_price
        self.tentative_timestamp = tentative_ts
        self.changed = True
        self._set_initialized(True)

    def _confirm_pivot(
        self,
        confirmed_dir: int,
        new_tentative_price: float,
        new_tentative_ts: int,
        new_direction: int,
    ) -> None:
        pivot = ZigZagPivot(
            price=self.tentative_price,
            timestamp=self.tentative_timestamp,
            direction=confirmed_dir,
            bar_index=self._bar_count,
        )
        self._pivots.append(pivot)
        self.pivot_price = self.tentative_price
        self.pivot_timestamp = self.tentative_timestamp
        self.pivot_direction = confirmed_dir
        self.pivot_count += 1
        self.changed = True
        self.direction = new_direction
        self.tentative_price = new_tentative_price
        self.tentative_timestamp = new_tentative_ts

    def _reset(self) -> None:
        if isinstance(self._pivots, deque):
            self._pivots.clear()
        else:
            self._pivots = []
        self._bar_count = 0
        self._initial_high = 0.0
        self._initial_low = 0.0
        self._initial_high_ts = 0
        self._initial_low_ts = 0
        self.direction = 0
        self.changed = False
        self.pivot_price = 0.0
        self.pivot_timestamp = 0
        self.pivot_direction = 0
        self.tentative_price = 0.0
        self.tentative_timestamp = 0
        self.pivot_count = 0
        if self._atr is not None:
            self._atr.reset()
