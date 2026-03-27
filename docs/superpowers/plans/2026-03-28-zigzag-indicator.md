# ZigZag Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a threshold-based ZigZag indicator to `packages/indicators/` that identifies significant price reversals in both percentage and ATR modes.

**Architecture:** Pure Python `ZigZagIndicator(Indicator)` class in `packages/indicators/indicators/zigzag/`. Frozen dataclass `ZigZagPivot` for pivot data. Follows the Key Levels indicator pattern.

**Tech Stack:** Python, pytest, nautilus_trader indicator base class, existing bar_factory test helpers

**Spec:** `docs/superpowers/specs/2026-03-28-zigzag-indicator-design.md`

**Working directory:** All paths relative to `packages/indicators/` unless otherwise noted.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `indicators/zigzag/__init__.py` | Create | Public exports: `ZigZagPivot`, `ZigZagIndicator` |
| `indicators/zigzag/model.py` | Create | `ZigZagPivot` frozen dataclass |
| `indicators/zigzag/indicator.py` | Create | `ZigZagIndicator(Indicator)` implementation |
| `tests/zigzag/__init__.py` | Create | Test package marker |
| `tests/zigzag/test_model.py` | Create | ZigZagPivot tests |
| `tests/zigzag/test_indicator.py` | Create | All indicator tests |

---

### Task 1: Create ZigZagPivot data model

**Files:**
- Create: `indicators/zigzag/__init__.py`
- Create: `indicators/zigzag/model.py`
- Create: `tests/zigzag/__init__.py`
- Create: `tests/zigzag/test_model.py`

- [ ] **Step 1: Create the model file**

Create `indicators/zigzag/model.py`:

```python
"""ZigZag pivot data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZigZagPivot:
    """A confirmed zigzag pivot point.

    Parameters
    ----------
    price : float
        The pivot price (high or low).
    timestamp : int
        Nanosecond timestamp (bar.ts_init) when the pivot was set.
    direction : int
        1 = swing high, -1 = swing low.
    bar_index : int
        Bar count when pivot was confirmed.
    """

    price: float
    timestamp: int
    direction: int
    bar_index: int
```

- [ ] **Step 2: Create the package __init__.py**

Create `indicators/zigzag/__init__.py`:

```python
"""ZigZag indicator — threshold-based reversal detection."""

from indicators.zigzag.model import ZigZagPivot

__all__ = ["ZigZagPivot"]
```

- [ ] **Step 3: Write model tests**

Create `tests/zigzag/__init__.py` (empty file).

Create `tests/zigzag/test_model.py`:

```python
"""Tests for ZigZagPivot data model."""

import dataclasses

import pytest

from indicators.zigzag.model import ZigZagPivot


class TestZigZagPivot:
    def test_create_pivot(self):
        pivot = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)

        assert pivot.price == 110.0
        assert pivot.timestamp == 1_000_000
        assert pivot.direction == 1
        assert pivot.bar_index == 5

    def test_frozen_immutability(self):
        pivot = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)

        with pytest.raises(dataclasses.FrozenInstanceError):
            pivot.price = 120.0  # type: ignore[misc]

    def test_equality(self):
        a = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)
        b = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)

        assert a == b

    def test_inequality_different_price(self):
        a = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)
        b = ZigZagPivot(price=115.0, timestamp=1_000_000, direction=1, bar_index=5)

        assert a != b
```

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators
uv run pytest tests/zigzag/test_model.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add indicators/zigzag/ tests/zigzag/
git commit -m "feat(indicators): add ZigZagPivot data model and tests"
```

---

### Task 2: Implement ZigZagIndicator

**Files:**
- Create: `indicators/zigzag/indicator.py`
- Modify: `indicators/zigzag/__init__.py`

- [ ] **Step 1: Create the indicator implementation**

Create `indicators/zigzag/indicator.py`:

```python
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
            # Extend tentative if new high
            if high > self.tentative_price:
                self.tentative_price = high
                self.tentative_timestamp = ts_ns
                # Recompute if TENTATIVE base
                if self._mode == "PERCENTAGE" and self._threshold_base == "TENTATIVE":
                    effective_threshold = self.tentative_price * self.threshold

            # Check for reversal down
            if low <= self.tentative_price - effective_threshold:
                self._confirm_pivot(1, low, ts_ns, -1)

        elif self.direction == -1:
            # Extend tentative if new low
            if low < self.tentative_price:
                self.tentative_price = low
                self.tentative_timestamp = ts_ns
                # Recompute if TENTATIVE base
                if self._mode == "PERCENTAGE" and self._threshold_base == "TENTATIVE":
                    effective_threshold = self.tentative_price * self.threshold

            # Check for reversal up
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
```

- [ ] **Step 2: Update __init__.py exports**

Update `indicators/zigzag/__init__.py`:

```python
"""ZigZag indicator — threshold-based reversal detection."""

from indicators.zigzag.indicator import ZigZagIndicator
from indicators.zigzag.model import ZigZagPivot

__all__ = ["ZigZagIndicator", "ZigZagPivot"]
```

- [ ] **Step 3: Commit**

```bash
git add indicators/zigzag/
git commit -m "feat(indicators): implement ZigZagIndicator"
```

---

### Task 3: Write indicator tests — instantiation and validation

**Files:**
- Create: `tests/zigzag/test_indicator.py`

- [ ] **Step 1: Write instantiation and validation tests**

Create `tests/zigzag/test_indicator.py`:

```python
"""Tests for ZigZagIndicator."""

import pytest

from indicators.zigzag.indicator import ZigZagIndicator
from tests.helpers.bar_factory import make_bar, make_bars_from_ohlcv, _BASE_TS, _1H_NS


class TestZigZagInstantiation:
    def test_name(self):
        zz = ZigZagIndicator(0.05)
        assert zz.name == "ZigZagIndicator"

    def test_repr_percentage_mode(self):
        zz = ZigZagIndicator(0.05)
        assert str(zz) == "ZigZagIndicator(0.05,PERCENTAGE,14,PIVOT,10000)"

    def test_repr_atr_mode(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=20)
        assert str(zz) == "ZigZagIndicator(2.0,ATR,20,PIVOT,10000)"

    def test_default_properties(self):
        zz = ZigZagIndicator(0.05)
        assert zz.threshold == 0.05
        assert zz.atr_period == 14
        assert zz.max_pivots == 10000
        assert zz.direction == 0
        assert zz.changed is False
        assert zz.initialized is False
        assert zz.has_inputs is False
        assert zz.pivot_price == 0.0
        assert zz.pivot_timestamp == 0
        assert zz.pivot_direction == 0
        assert zz.tentative_price == 0.0
        assert zz.tentative_timestamp == 0
        assert zz.pivot_count == 0
        assert zz.pivots == []

    def test_unlimited_pivots(self):
        zz = ZigZagIndicator(0.05, max_pivots=0)
        assert zz.max_pivots == 0

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ZigZagIndicator(0.05, mode="INVALID")

    def test_invalid_threshold_base_raises(self):
        with pytest.raises(ValueError):
            ZigZagIndicator(0.05, threshold_base="INVALID")

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError):
            ZigZagIndicator(-0.05)

    def test_negative_max_pivots_raises(self):
        with pytest.raises(ValueError):
            ZigZagIndicator(0.05, max_pivots=-1)
```

- [ ] **Step 2: Run tests**

```bash
cd packages/indicators
uv run pytest tests/zigzag/test_indicator.py::TestZigZagInstantiation -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/zigzag/test_indicator.py
git commit -m "test(indicators): add ZigZag instantiation and validation tests"
```

---

### Task 4: Write indicator tests — percentage mode reversals

**Files:**
- Modify: `tests/zigzag/test_indicator.py`

- [ ] **Step 1: Add percentage mode tests**

Append to `tests/zigzag/test_indicator.py`:

```python
class TestZigZagPercentageMode:
    def setup_method(self):
        self.zz = ZigZagIndicator(0.05)  # 5% threshold

    def test_has_inputs_after_first_bar(self):
        bar = make_bar(100.0, 101.0, 99.0, 100.5)
        self.zz.handle_bar(bar)
        assert self.zz.has_inputs is True
        assert self.zz.initialized is False

    def test_first_reversal_from_high(self):
        # Price rises to 110, then drops >5% (110 * 0.05 = 5.5)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),   # bar 0
            (103.0, 105.0, 100.0, 103.0, 100), # bar 1
            (107.0, 110.0, 104.0, 107.0, 100), # bar 2: high=110
            (104.5, 105.0, 104.0, 104.5, 100), # bar 3: low=104, drop=6 > 5.5
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.initialized is True
        assert self.zz.changed is True
        assert self.zz.direction == -1
        assert self.zz.pivot_price == 110.0
        assert self.zz.pivot_direction == 1
        assert self.zz.pivot_count == 1
        assert self.zz.tentative_price == 104.0

    def test_first_reversal_from_low(self):
        # Price drops to 90, then rises >5% (90 * 0.05 = 4.5)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (95.0, 97.0, 93.0, 95.0, 100),
            (91.0, 92.0, 90.0, 91.0, 100),   # low=90
            (94.0, 95.0, 91.0, 94.0, 100),   # high=95, rise=5 > 4.5
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.initialized is True
        assert self.zz.changed is True
        assert self.zz.direction == 1
        assert self.zz.pivot_price == 90.0
        assert self.zz.pivot_direction == -1
        assert self.zz.pivot_count == 1

    def test_extending_tentative_no_confirmation(self):
        # Initialize, then extend down leg without reversal
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # reversal: pivot at 110
            (103.0, 104.0, 102.0, 103.0, 100),   # extends tentative to 102
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.changed is False
        assert self.zz.tentative_price == 102.0
        assert self.zz.pivot_count == 1

    def test_full_zigzag_sequence(self):
        # Up to 110, reversal down, down to 100, reversal up
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),   # high=110
            (104.5, 105.0, 104.0, 104.5, 100),    # reversal 1
            (101.0, 103.0, 100.0, 101.0, 100),    # tentative=100
            (105.0, 106.0, 101.0, 105.0, 100),    # reversal 2 (PIVOT base: 110*0.05=5.5, 106>=100+5.5)
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.pivot_count == 2
        assert self.zz.pivot_price == 100.0
        assert self.zz.pivot_direction == -1
        assert self.zz.direction == 1
        assert self.zz.changed is True

    def test_changed_flag_resets_next_bar(self):
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # changed=True
            (104.0, 105.0, 103.0, 104.0, 100),  # next bar
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.changed is False
```

- [ ] **Step 2: Run tests**

```bash
cd packages/indicators
uv run pytest tests/zigzag/test_indicator.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/zigzag/test_indicator.py
git commit -m "test(indicators): add ZigZag percentage mode reversal tests"
```

---

### Task 5: Write indicator tests — ATR mode, threshold_base, max_pivots, reset

**Files:**
- Modify: `tests/zigzag/test_indicator.py`

- [ ] **Step 1: Add remaining tests**

Append to `tests/zigzag/test_indicator.py`:

```python
class TestZigZagATRMode:
    def test_not_initialized_until_atr_warmed_up(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=3)
        bars = make_bars_from_ohlcv([
            (100.0, 102.0, 98.0, 100.0, 100),
            (100.0, 101.0, 99.0, 100.0, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.has_inputs is True
        assert zz.initialized is False
        assert zz.direction == 0

    def test_reversal_after_atr_warmup(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=3)
        bars = make_bars_from_ohlcv([
            (100.0, 102.0, 98.0, 100.0, 100),   # TR=4
            (100.0, 101.0, 99.0, 100.0, 100),   # TR=2
            (105.0, 110.0, 100.0, 105.0, 100),  # TR=10, ATR~5.33
            (100.0, 105.0, 98.0, 100.0, 100),   # drop from 110, 110-98=12 > 2*5.33
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.initialized is True
        assert zz.direction == -1
        assert zz.pivot_direction == 1
        assert zz.pivot_count >= 1


class TestZigZagThresholdBase:
    def test_tentative_base_easier_reversal(self):
        # TENTATIVE base: threshold from tentative (lower), so easier to reverse
        zz = ZigZagIndicator(0.05, threshold_base="TENTATIVE")
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # pivot at 110
            (101.0, 103.0, 100.0, 101.0, 100),  # tentative=100
            # TENTATIVE: 100*0.05=5.0, need high>=105. With 105.5 => reversal
            (104.0, 105.5, 101.0, 104.0, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_count == 2
        assert zz.direction == 1

    def test_pivot_base_harder_reversal(self):
        # PIVOT base: threshold from pivot_price=110, so harder
        zz = ZigZagIndicator(0.05, threshold_base="PIVOT")
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # pivot at 110
            (101.0, 103.0, 100.0, 101.0, 100),  # tentative=100
            # PIVOT: 110*0.05=5.5, need high>=105.5. With 105.0 => NO reversal
            (104.0, 105.0, 101.0, 104.0, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_count == 1  # Not reversed yet
        assert zz.direction == -1


class TestZigZagMaxPivots:
    def test_evicts_oldest_when_full(self):
        zz = ZigZagIndicator(0.05, max_pivots=2)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),    # pivot 1: 110 (high)
            (101.0, 103.0, 100.0, 101.0, 100),
            (105.0, 106.0, 101.0, 105.0, 100),    # pivot 2: 100 (low)
            (112.0, 115.0, 106.0, 112.0, 100),
            (109.0, 112.0, 108.0, 109.0, 100),    # pivot 3: 115 (high)
        ])
        for bar in bars:
            zz.handle_bar(bar)

        pivots = zz.pivots
        assert len(pivots) == 2
        assert pivots[0].price == 100.0   # pivot 2 (oldest surviving)
        assert pivots[1].price == 115.0   # pivot 3


class TestZigZagEdgeCases:
    def test_tentative_repaints_confirmed_does_not(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # pivot at 110
            (102.0, 103.0, 101.0, 102.0, 100),  # tentative extends to 101
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_price == 110.0    # confirmed — unchanged
        assert zz.tentative_price == 101.0  # repainted

    def test_timestamp_tracking(self):
        zz = ZigZagIndicator(0.05)
        ts = [_BASE_TS + i * _1H_NS for i in range(5)]
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),   # high=110 at ts[1]
            (104.5, 105.0, 104.0, 104.5, 100),    # reversal at ts[2]
            (102.0, 103.0, 101.0, 102.0, 100),    # tentative extends at ts[3]
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_timestamp == ts[1]      # when high was set
        assert zz.tentative_timestamp == ts[3]   # latest extension

    def test_multiple_pivots_in_history(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),    # pivot 1: 110
            (101.0, 103.0, 100.0, 101.0, 100),
            (105.0, 106.0, 101.0, 105.0, 100),    # pivot 2: 100
            (112.0, 115.0, 106.0, 112.0, 100),
            (109.0, 112.0, 108.0, 109.0, 100),    # pivot 3: 115
        ])
        for bar in bars:
            zz.handle_bar(bar)

        pivots = zz.pivots
        assert len(pivots) == 3
        assert pivots[0].price == 110.0
        assert pivots[0].direction == 1
        assert pivots[1].price == 100.0
        assert pivots[1].direction == -1
        assert pivots[2].price == 115.0
        assert pivots[2].direction == 1

    def test_pivots_returns_copy(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        pivots = zz.pivots
        pivots.clear()
        assert len(zz.pivots) == 1  # internal unaffected


class TestZigZagReset:
    def test_reset_clears_all_state(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)
        assert zz.initialized is True

        zz.reset()

        assert zz.has_inputs is False
        assert zz.initialized is False
        assert zz.direction == 0
        assert zz.changed is False
        assert zz.pivot_price == 0.0
        assert zz.pivot_timestamp == 0
        assert zz.pivot_direction == 0
        assert zz.tentative_price == 0.0
        assert zz.tentative_timestamp == 0
        assert zz.pivot_count == 0
        assert zz.pivots == []

    def test_reset_atr_mode(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=3)
        bar = make_bar(100.0, 102.0, 98.0, 100.0)
        zz.handle_bar(bar)

        zz.reset()

        assert zz.has_inputs is False
        assert zz.initialized is False
```

- [ ] **Step 2: Run all tests**

```bash
cd packages/indicators
uv run pytest tests/zigzag/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/zigzag/test_indicator.py
git commit -m "test(indicators): add ZigZag ATR, threshold_base, max_pivots, edge case, and reset tests"
```

---

### Task 6: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full indicator test suite**

```bash
cd packages/indicators
uv run pytest tests/ -v
```

Expected: All tests pass — both ZigZag and any existing Key Levels tests.

- [ ] **Step 2: Import smoke test**

```bash
cd packages/indicators
uv run python -c "
from indicators.zigzag import ZigZagIndicator, ZigZagPivot
from tests.helpers.bar_factory import make_bars_from_ohlcv

zz = ZigZagIndicator(0.05)
bars = make_bars_from_ohlcv([
    (99.0, 100.0, 98.0, 99.0, 100),
    (105.0, 110.0, 100.0, 105.0, 100),
    (104.5, 105.0, 104.0, 104.5, 100),
])
for bar in bars:
    zz.handle_bar(bar)

print(f'Repr: {zz}')
print(f'Initialized: {zz.initialized}')
print(f'Pivot count: {zz.pivot_count}')
print(f'Last pivot: {zz.pivot_price} ({"HIGH" if zz.pivot_direction == 1 else "LOW"})')
print(f'Direction: {zz.direction}')
print(f'Tentative: {zz.tentative_price}')
print(f'Pivots: {zz.pivots}')
"
```

Expected:
```
Repr: ZigZagIndicator(0.05,PERCENTAGE,14,PIVOT,10000)
Initialized: True
Pivot count: 1
Last pivot: 110.0 (HIGH)
Direction: -1
Tentative: 104.0
Pivots: [ZigZagPivot(price=110.0, timestamp=..., direction=1, bar_index=2)]
```
