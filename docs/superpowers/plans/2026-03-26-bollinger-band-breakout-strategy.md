# Bollinger Band Breakout Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Bollinger Band Breakout (BBB) strategy from Rust automatron to Python for NautilusTrader BacktestEngine, producing feather files readable by the existing dashboard.

**Architecture:** NautilusTrader `Strategy` subclass with two `BollingerBands` indicator instances (buy/sell), crossover detection via previous-bar tracking, and frequency delay control. Jupyter notebook configures `BacktestEngine` with `StreamingConfig` to write feather output to the catalog. Phase 1 implements Baseline mode; Phase 2 adds Breakout mode with MA trend filtering.

**Tech Stack:** Python 3.12+, nautilus_trader (BacktestEngine, BollingerBands indicator, Strategy), Jupyter, uv for dependency management

---

## File Structure

### New Files
- `packages/runner/pyproject.toml` — Python package config with nautilus_trader + jupyter deps
- `packages/runner/runner/__init__.py` — Package init
- `packages/runner/runner/strategies/__init__.py` — Strategies subpackage init
- `packages/runner/runner/strategies/bbb_strategy.py` — BBBStrategyConfig + BBBStrategy (Baseline + Breakout)
- `packages/runner/runner/strategies/ma_trend.py` — MA trend direction calculation (for Breakout mode)
- `packages/runner/tests/__init__.py` — Test package init
- `packages/runner/tests/test_bbb_strategy.py` — Unit tests for BBB strategy logic
- `packages/runner/tests/test_ma_trend.py` — Unit tests for MA trend
- `packages/runner/runner/bbb_backtest.ipynb` — Jupyter notebook for running backtests

### Reference Files (read-only)
- `nautilus_trader/nautilus_trader/examples/strategies/bb_mean_reversion.py` — NautilusTrader BB strategy pattern
- `automatron/src/strategy/bollinger_band_breakout.rs` — Original Rust BBB logic
- `automatron/src/strategy/bollinger_band_breakout/bollinger_band_breakout_variant.rs` — Rust config/variant
- `automatron/src/indicators/ma_trend_direction.rs` — Rust MA trend logic

---

## Task 1: Runner Package Setup

**Files:**
- Create: `packages/runner/pyproject.toml`
- Create: `packages/runner/runner/__init__.py`
- Create: `packages/runner/runner/strategies/__init__.py`
- Create: `packages/runner/tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "nautilus-automatron-runner"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "nautilus_trader",
    "pandas>=2.2.0",
    "pyarrow>=18.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "jupyter>=1.0.0",
    "ipykernel>=6.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create __init__.py files**

`packages/runner/runner/__init__.py`:
```python
```

`packages/runner/runner/strategies/__init__.py`:
```python
```

`packages/runner/tests/__init__.py`:
```python
```

- [ ] **Step 3: Install dependencies**

```bash
cd packages/runner && uv sync
```

- [ ] **Step 4: Verify nautilus_trader imports work**

```bash
cd packages/runner && uv run python -c "from nautilus_trader.indicators import BollingerBands; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add packages/runner/pyproject.toml packages/runner/runner/__init__.py packages/runner/runner/strategies/__init__.py packages/runner/tests/__init__.py
git commit -m "feat: scaffold runner package with nautilus_trader dependency"
```

---

## Task 2: BBB Strategy Config and Enums

**Files:**
- Create: `packages/runner/runner/strategies/bbb_strategy.py`
- Create: `packages/runner/tests/test_bbb_strategy.py`

- [ ] **Step 1: Write tests for config creation**

`packages/runner/tests/test_bbb_strategy.py`:
```python
from decimal import Decimal

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from runner.strategies.bbb_strategy import (
    ArrayKind,
    BandKind,
    BBBSignalVariant,
    BBBStrategyConfig,
    MATrendKind,
)


def test_config_defaults():
    config = BBBStrategyConfig(
        instrument_id=InstrumentId.from_str("XAU/USD.SIM"),
        bar_type=BarType.from_str("XAU/USD.SIM-5-MINUTE-BID-EXTERNAL"),
        trade_size=Decimal("1"),
    )
    assert config.buy_array_kind == ArrayKind.CLOSE
    assert config.buy_band_kind == BandKind.TOP
    assert config.buy_period == 20
    assert config.buy_sd == 2.0
    assert config.sell_array_kind == ArrayKind.CLOSE
    assert config.sell_band_kind == BandKind.TOP
    assert config.sell_period == 20
    assert config.sell_sd == 2.0
    assert config.frequency_bars == 10
    assert config.signal_variant == BBBSignalVariant.BASELINE
    assert config.ma_trend_kind == MATrendKind.NORMAL


def test_config_custom_params():
    config = BBBStrategyConfig(
        instrument_id=InstrumentId.from_str("XAU/USD.SIM"),
        bar_type=BarType.from_str("XAU/USD.SIM-5-MINUTE-BID-EXTERNAL"),
        trade_size=Decimal("1"),
        buy_band_kind=BandKind.BOTTOM,
        buy_sd=1.0,
        sell_sd=3.0,
        signal_variant=BBBSignalVariant.BREAKOUT,
        ma_trend_kind=MATrendKind.FAST,
    )
    assert config.buy_band_kind == BandKind.BOTTOM
    assert config.buy_sd == 1.0
    assert config.sell_sd == 3.0
    assert config.signal_variant == BBBSignalVariant.BREAKOUT
    assert config.ma_trend_kind == MATrendKind.FAST
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'runner.strategies.bbb_strategy'`

- [ ] **Step 3: Implement config and enums**

`packages/runner/runner/strategies/bbb_strategy.py`:
```python
from decimal import Decimal
from enum import Enum

from nautilus_trader.config import PositiveFloat, PositiveInt, StrategyConfig
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId


class ArrayKind(Enum):
    CLOSE = "close"
    HIGH = "high"
    LOW = "low"
    OPEN = "open"


class BandKind(Enum):
    TOP = "top"
    BOTTOM = "bottom"


class BBBSignalVariant(Enum):
    BASELINE = "baseline"
    BREAKOUT = "breakout"


class MATrendKind(Enum):
    IMMEDIATE = "immediate"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"


class BBBStrategyConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    # Buy params
    buy_array_kind: ArrayKind = ArrayKind.CLOSE
    buy_band_kind: BandKind = BandKind.TOP
    buy_period: PositiveInt = 20
    buy_sd: PositiveFloat = 2.0
    # Sell params
    sell_array_kind: ArrayKind = ArrayKind.CLOSE
    sell_band_kind: BandKind = BandKind.TOP
    sell_period: PositiveInt = 20
    sell_sd: PositiveFloat = 2.0
    # Control
    frequency_bars: PositiveInt = 10
    signal_variant: BBBSignalVariant = BBBSignalVariant.BASELINE
    ma_trend_kind: MATrendKind = MATrendKind.NORMAL
    close_positions_on_stop: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/runner/runner/strategies/bbb_strategy.py packages/runner/tests/test_bbb_strategy.py
git commit -m "feat: add BBB strategy config with enums for array/band/signal variants"
```

---

## Task 3: BBB Strategy — Baseline Entry/Exit Logic

**Files:**
- Modify: `packages/runner/runner/strategies/bbb_strategy.py`
- Modify: `packages/runner/tests/test_bbb_strategy.py`

- [ ] **Step 1: Write test for crossover detection helpers**

Append to `packages/runner/tests/test_bbb_strategy.py`:
```python
from runner.strategies.bbb_strategy import is_cross_above, is_cross_below


def test_cross_above_detected():
    # prev bar: price below band, current bar: price >= band
    prices = [100.0, 98.0, 102.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_above(prices, bands, 2) is True


def test_cross_above_not_detected_when_already_above():
    prices = [100.0, 101.0, 102.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_above(prices, bands, 2) is False


def test_cross_below_detected():
    # prev bar: price above band, current bar: price <= band
    prices = [100.0, 102.0, 98.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_below(prices, bands, 2) is True


def test_cross_below_not_detected_when_already_below():
    prices = [100.0, 98.0, 97.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_below(prices, bands, 2) is False


def test_cross_above_at_boundary():
    # prev bar: price < band, current bar: price == band (exact touch counts)
    prices = [99.0, 100.0]
    bands = [100.0, 100.0]
    assert is_cross_above(prices, bands, 1) is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py::test_cross_above_detected -v
```

Expected: FAIL — `ImportError: cannot import name 'is_cross_above'`

- [ ] **Step 3: Implement crossover functions**

Add to `packages/runner/runner/strategies/bbb_strategy.py`:
```python
def is_cross_above(prices: list[float], bands: list[float], index: int) -> bool:
    prev_price = prices[index - 1]
    prev_band = bands[index - 1]
    curr_price = prices[index]
    curr_band = bands[index]
    return prev_price < prev_band and curr_price >= curr_band


def is_cross_below(prices: list[float], bands: list[float], index: int) -> bool:
    prev_price = prices[index - 1]
    prev_band = bands[index - 1]
    curr_price = prices[index]
    curr_band = bands[index]
    return prev_price > prev_band and curr_price <= curr_band
```

- [ ] **Step 4: Run crossover tests**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py -k "cross" -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add packages/runner/runner/strategies/bbb_strategy.py packages/runner/tests/test_bbb_strategy.py
git commit -m "feat: add crossover detection functions for BBB strategy"
```

---

## Task 4: BBB Strategy Class — Core on_bar with Baseline Mode

**Files:**
- Modify: `packages/runner/runner/strategies/bbb_strategy.py`
- Modify: `packages/runner/tests/test_bbb_strategy.py`

- [ ] **Step 1: Write integration test for strategy baseline signals**

Append to `packages/runner/tests/test_bbb_strategy.py`:
```python
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from nautilus_trader.indicators import BollingerBands
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide

from runner.strategies.bbb_strategy import BBBStrategy, BBBStrategyConfig, BandKind


def make_config(**overrides) -> BBBStrategyConfig:
    defaults = dict(
        instrument_id=InstrumentId.from_str("XAU/USD.SIM"),
        bar_type=BarType.from_str("XAU/USD.SIM-5-MINUTE-BID-EXTERNAL"),
        trade_size=Decimal("1"),
    )
    defaults.update(overrides)
    return BBBStrategyConfig(**defaults)


def test_strategy_creates_two_bb_indicators():
    config = make_config(buy_period=20, buy_sd=1.0, sell_period=20, sell_sd=3.0)
    strategy = BBBStrategy(config=config)
    assert strategy.buy_bb.period == 20
    assert strategy.buy_bb.k == 1.0
    assert strategy.sell_bb.period == 20
    assert strategy.sell_bb.k == 3.0


def test_strategy_tracks_previous_bar_values():
    config = make_config()
    strategy = BBBStrategy(config=config)
    assert strategy._prev_close is None
    assert strategy._prev_high is None
    assert strategy._prev_low is None
    assert strategy._bars_since_entry == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py::test_strategy_creates_two_bb_indicators -v
```

Expected: FAIL — `ImportError: cannot import name 'BBBStrategy'`

- [ ] **Step 3: Implement BBBStrategy class**

Add to `packages/runner/runner/strategies/bbb_strategy.py` (after the config class and crossover functions):
```python
from nautilus_trader.common.enums import LogColor
from nautilus_trader.indicators import BollingerBands
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


def _get_price_from_bar(bar: Bar, array_kind: ArrayKind) -> float:
    match array_kind:
        case ArrayKind.CLOSE:
            return bar.close.as_double()
        case ArrayKind.HIGH:
            return bar.high.as_double()
        case ArrayKind.LOW:
            return bar.low.as_double()
        case ArrayKind.OPEN:
            return bar.open.as_double()


def _get_band_value(bb: BollingerBands, band_kind: BandKind) -> float:
    match band_kind:
        case BandKind.TOP:
            return bb.upper
        case BandKind.BOTTOM:
            return bb.lower


class BBBStrategy(Strategy):

    def __init__(self, config: BBBStrategyConfig) -> None:
        super().__init__(config)
        self.instrument: Instrument | None = None

        # Two separate BB indicator instances (buy/sell can have different period/SD)
        self.buy_bb = BollingerBands(config.buy_period, config.buy_sd)
        self.sell_bb = BollingerBands(config.sell_period, config.sell_sd)

        # Previous bar tracking for crossover detection
        self._prev_buy_price: float | None = None
        self._prev_buy_band: float | None = None
        self._prev_sell_price: float | None = None
        self._prev_sell_band: float | None = None
        self._prev_close: float | None = None
        self._prev_high: float | None = None
        self._prev_low: float | None = None

        # Frequency control
        self._bars_since_entry: int = 0
        self._has_position: bool = False

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return

        self.register_indicator_for_bars(self.config.bar_type, self.buy_bb)
        self.register_indicator_for_bars(self.config.bar_type, self.sell_bb)
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            self.log.info(
                f"Waiting for indicators to warm up [{self.cache.bar_count(self.config.bar_type)}]",
                color=LogColor.BLUE,
            )
            return

        if bar.is_single_price():
            return

        buy_price = _get_price_from_bar(bar, self.config.buy_array_kind)
        buy_band = _get_band_value(self.buy_bb, self.config.buy_band_kind)
        sell_price = _get_price_from_bar(bar, self.config.sell_array_kind)
        sell_band = _get_band_value(self.sell_bb, self.config.sell_band_kind)

        self._bars_since_entry += 1

        if self._prev_buy_price is not None:
            self._check_signals(buy_price, buy_band, sell_price, sell_band)

        # Store current values for next bar's crossover detection
        self._prev_buy_price = buy_price
        self._prev_buy_band = buy_band
        self._prev_sell_price = sell_price
        self._prev_sell_band = sell_band
        self._prev_close = bar.close.as_double()
        self._prev_high = bar.high.as_double()
        self._prev_low = bar.low.as_double()

    def _check_signals(
        self,
        buy_price: float,
        buy_band: float,
        sell_price: float,
        sell_band: float,
    ) -> None:
        is_long = self.portfolio.is_net_long(self.config.instrument_id)

        # Exit check first (always check, no frequency limit)
        if is_long:
            is_exit = (
                self._prev_sell_price > self._prev_sell_band
                and sell_price <= sell_band
            )
            if is_exit:
                self.close_all_positions(self.config.instrument_id)
                self._has_position = False
                return

        # Entry check (respects frequency delay)
        if not is_long:
            is_entry = (
                self._prev_buy_price < self._prev_buy_band
                and buy_price >= buy_band
            )
            frequency_ok = self._bars_since_entry >= self.config.frequency_bars

            if is_entry and frequency_ok:
                self._enter_long()

    def _enter_long(self) -> None:
        order: MarketOrder = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            time_in_force=TimeInForce.GTC,
        )
        self.submit_order(order)
        self._bars_since_entry = 0
        self._has_position = True

    def on_stop(self) -> None:
        self.cancel_all_orders(self.config.instrument_id)
        if self.config.close_positions_on_stop:
            self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        self.buy_bb.reset()
        self.sell_bb.reset()
        self._prev_buy_price = None
        self._prev_buy_band = None
        self._prev_sell_price = None
        self._prev_sell_band = None
        self._prev_close = None
        self._prev_high = None
        self._prev_low = None
        self._bars_since_entry = 0
        self._has_position = False
```

- [ ] **Step 4: Run tests**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/runner/runner/strategies/bbb_strategy.py packages/runner/tests/test_bbb_strategy.py
git commit -m "feat: implement BBBStrategy with baseline entry/exit crossover logic"
```

---

## Task 5: MA Trend Direction (for Breakout Mode)

**Files:**
- Create: `packages/runner/runner/strategies/ma_trend.py`
- Create: `packages/runner/tests/test_ma_trend.py`

- [ ] **Step 1: Write tests for MA trend calculation**

`packages/runner/tests/test_ma_trend.py`:
```python
from runner.strategies.ma_trend import (
    TrendDirection,
    calculate_gradients,
    get_trend_direction,
)


THRESHOLD = 0.02


def test_calculate_gradients_basic():
    data = [100.0, 101.0, 102.0, 103.0]
    gradients = calculate_gradients(data)
    # dy=1.0, dx=2.0, gradient=0.5 for each step
    assert len(gradients) == 3
    assert all(g == 0.5 for g in gradients)


def test_calculate_gradients_empty():
    assert calculate_gradients([]) == []
    assert calculate_gradients([100.0]) == []


def test_trend_direction_up_when_consecutive_positive():
    # 5 consecutive positive gradients → UP
    gradients = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    result = get_trend_direction(gradients, bar=6, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.UP


def test_trend_direction_down_when_consecutive_negative():
    gradients = [-0.5, -0.5, -0.5, -0.5, -0.5, -0.5, -0.5]
    result = get_trend_direction(gradients, bar=6, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.DOWN


def test_trend_direction_flat_when_mixed():
    gradients = [0.5, -0.5, 0.5, -0.5, 0.5, 0.5, 0.5]
    result = get_trend_direction(gradients, bar=6, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.FLAT


def test_trend_direction_flat_when_insufficient_bars():
    gradients = [0.5, 0.5]
    result = get_trend_direction(gradients, bar=1, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.FLAT


def test_trend_direction_flat_within_threshold():
    # Gradients within threshold count as flat
    gradients = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01]
    result = get_trend_direction(gradients, bar=5, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.FLAT
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/runner && uv run pytest tests/test_ma_trend.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MA trend module**

`packages/runner/runner/strategies/ma_trend.py`:
```python
from enum import Enum


GRADIENT_THRESHOLD = 0.02
FAST_LOOKBACK = 5
NORMAL_LOOKBACK = 5
SLOW_LOOKBACK = 5


class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


def calculate_gradients(data: list[float]) -> list[float]:
    if len(data) < 2:
        return []
    gradients: list[float] = []
    for i in range(1, len(data)):
        dy = data[i] - data[i - 1]
        dx = 2.0  # 2 bars equivalent, matching Rust implementation
        gradients.append(dy / dx)
    return gradients


def _gradient_to_direction(gradient: float, threshold: float) -> TrendDirection:
    if gradient > threshold:
        return TrendDirection.UP
    elif gradient < -threshold:
        return TrendDirection.DOWN
    return TrendDirection.FLAT


def get_trend_direction(
    gradients: list[float],
    bar: int,
    lookback: int,
    threshold: float = GRADIENT_THRESHOLD,
) -> TrendDirection:
    if bar < lookback:
        return TrendDirection.FLAT

    current_direction = _gradient_to_direction(gradients[bar], threshold)
    if current_direction == TrendDirection.FLAT:
        return TrendDirection.FLAT

    for i in range(bar - lookback, bar):
        if _gradient_to_direction(gradients[i], threshold) != current_direction:
            return TrendDirection.FLAT

    return current_direction
```

- [ ] **Step 4: Run tests**

```bash
cd packages/runner && uv run pytest tests/test_ma_trend.py -v
```

Expected: All 7 tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/runner/runner/strategies/ma_trend.py packages/runner/tests/test_ma_trend.py
git commit -m "feat: add MA trend direction calculation for BBB breakout mode"
```

---

## Task 6: BBB Strategy — Breakout Mode Integration

**Files:**
- Modify: `packages/runner/runner/strategies/bbb_strategy.py`
- Modify: `packages/runner/tests/test_bbb_strategy.py`

- [ ] **Step 1: Write tests for breakout mode signal gating**

Append to `packages/runner/tests/test_bbb_strategy.py`:
```python
from runner.strategies.bbb_strategy import BBBSignalVariant, MATrendKind
from runner.strategies.ma_trend import TrendDirection


def test_strategy_breakout_config():
    config = make_config(
        signal_variant=BBBSignalVariant.BREAKOUT,
        ma_trend_kind=MATrendKind.NORMAL,
    )
    strategy = BBBStrategy(config=config)
    assert strategy.config.signal_variant == BBBSignalVariant.BREAKOUT
    assert strategy.config.ma_trend_kind == MATrendKind.NORMAL
```

- [ ] **Step 2: Run test**

```bash
cd packages/runner && uv run pytest tests/test_bbb_strategy.py::test_strategy_breakout_config -v
```

Expected: PASS (config already supports these fields)

- [ ] **Step 3: Add breakout mode to strategy's _check_signals**

Update `_check_signals` in `packages/runner/runner/strategies/bbb_strategy.py` to add MA trend gating for breakout mode. Replace the `_check_signals` method with:

```python
    def _check_signals(
        self,
        buy_price: float,
        buy_band: float,
        sell_price: float,
        sell_band: float,
    ) -> None:
        is_long = self.portfolio.is_net_long(self.config.instrument_id)

        # Exit check first (always check, no frequency limit)
        if is_long:
            is_exit = (
                self._prev_sell_price > self._prev_sell_band
                and sell_price <= sell_band
            )

            # Breakout mode: also exit on MA trend down
            if self.config.signal_variant == BBBSignalVariant.BREAKOUT:
                ma_trend = self._get_ma_trend()
                if ma_trend == TrendDirection.DOWN:
                    is_exit = True

            if is_exit:
                self.close_all_positions(self.config.instrument_id)
                self._has_position = False
                return

        # Entry check (respects frequency delay)
        if not is_long:
            is_entry = (
                self._prev_buy_price < self._prev_buy_band
                and buy_price >= buy_band
            )
            frequency_ok = self._bars_since_entry >= self.config.frequency_bars

            # Breakout mode: entry gated by MA trend up
            if self.config.signal_variant == BBBSignalVariant.BREAKOUT:
                ma_trend = self._get_ma_trend()
                if ma_trend != TrendDirection.UP:
                    is_entry = False

            if is_entry and frequency_ok:
                self._enter_long()
```

Also add the `_get_ma_trend` method and required imports. Add to the `__init__` method:

```python
        # MA trend tracking (for Breakout mode)
        self._close_history: list[float] = []
```

Add the MA trend helper:
```python
    def _get_ma_trend(self) -> TrendDirection:
        from nautilus_trader.indicators import ExponentialMovingAverage
        from runner.strategies.ma_trend import (
            TrendDirection,
            calculate_gradients,
            get_trend_direction,
            FAST_LOOKBACK,
            NORMAL_LOOKBACK,
            SLOW_LOOKBACK,
            GRADIENT_THRESHOLD,
        )

        lookback_map = {
            MATrendKind.IMMEDIATE: FAST_LOOKBACK,
            MATrendKind.FAST: FAST_LOOKBACK,
            MATrendKind.NORMAL: NORMAL_LOOKBACK,
            MATrendKind.SLOW: SLOW_LOOKBACK,
        }

        if len(self._close_history) < 2:
            return TrendDirection.FLAT

        gradients = calculate_gradients(self._close_history)
        bar = len(gradients) - 1
        lookback = lookback_map[self.config.ma_trend_kind]

        return get_trend_direction(gradients, bar, lookback, GRADIENT_THRESHOLD)
```

Update `on_bar` to track close history (add before the `self._prev_buy_price = buy_price` line):
```python
        self._close_history.append(bar.close.as_double())
```

Update `on_reset` to clear close history:
```python
        self._close_history = []
```

- [ ] **Step 4: Run all tests**

```bash
cd packages/runner && uv run pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/runner/runner/strategies/bbb_strategy.py packages/runner/tests/test_bbb_strategy.py
git commit -m "feat: add breakout mode with MA trend gating to BBB strategy"
```

---

## Task 7: Backtest Jupyter Notebook

**Files:**
- Create: `packages/runner/runner/bbb_backtest.ipynb`

- [ ] **Step 1: Create the notebook**

Create `packages/runner/runner/bbb_backtest.ipynb` with these cells:

**Cell 1 (markdown):**
```markdown
# Bollinger Band Breakout — Backtest

Runs BBB strategy on XAUUSD 5-minute bars using NautilusTrader BacktestEngine.
Output goes to `backtest_catalog/` as feather files for the dashboard.
```

**Cell 2 (code) — Imports and setup:**
```python
import os
from decimal import Decimal
from pathlib import Path

import pandas as pd

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD, XAU
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import InstrumentId, Symbol, TraderId, Venue
from nautilus_trader.model.objects import Currency, Money, Price, Quantity
from nautilus_trader.persistence.config import StreamingConfig
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from runner.strategies.bbb_strategy import (
    ArrayKind,
    BandKind,
    BBBSignalVariant,
    BBBStrategy,
    BBBStrategyConfig,
    MATrendKind,
)
```

**Cell 3 (code) — Instrument definition:**
```python
SIM = Venue("SIM")

# XAUUSD instrument — gold priced in USD, 2 decimal precision
from nautilus_trader.model.instruments import CurrencyPair

XAUUSD_SIM = CurrencyPair(
    instrument_id=InstrumentId(Symbol("XAU/USD"), SIM),
    raw_symbol=Symbol("XAU/USD"),
    base_currency=Currency.from_str("XAU"),
    quote_currency=Currency.from_str("USD"),
    price_precision=2,
    size_precision=0,
    price_increment=Price.from_str("0.01"),
    size_increment=Quantity.from_int(1),
    lot_size=None,
    max_quantity=None,
    min_quantity=Quantity.from_int(1),
    max_price=None,
    min_price=None,
    margin_init=Decimal("0.03"),
    margin_maint=Decimal("0.03"),
    maker_fee=Decimal("0.00002"),
    taker_fee=Decimal("0.00002"),
    ts_event=0,
    ts_init=0,
)

bar_type = BarType.from_str("XAU/USD.SIM-5-MINUTE-BID-EXTERNAL")
print(f"Instrument: {XAUUSD_SIM.id}")
print(f"Bar type: {bar_type}")
```

**Cell 4 (code) — Load data:**
```python
# Load XAUUSD 5-minute bar data from CSV
# Expected columns: timestamp (or datetime), open, high, low, close, volume
# Adjust path to your data source
DATA_PATH = Path("../../../data/xauusd_5m.csv")  # Adjust this path

df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
df = df.set_index("timestamp")
df.index = pd.to_datetime(df.index, utc=True)

print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
df.head()
```

**Cell 5 (code) — Wrangle bars:**
```python
wrangler = BarDataWrangler(bar_type=bar_type, instrument=XAUUSD_SIM)
bars = wrangler.process(df)
print(f"Wrangled {len(bars)} bars")
```

**Cell 6 (code) — Configure and run engine:**
```python
CATALOG_PATH = os.environ.get(
    "NAUTILUS_STORE_PATH",
    str(Path.home() / "code" / "nautilus_trader" / "backtest_catalog"),
)

engine_config = BacktestEngineConfig(
    trader_id=TraderId("BACKTESTER-001"),
    logging=LoggingConfig(log_level="INFO"),
    streaming=StreamingConfig(
        catalog_path=CATALOG_PATH,
        replace_existing=True,
    ),
)

engine = BacktestEngine(config=engine_config)

engine.add_venue(
    venue=SIM,
    oms_type=OmsType.NETTING,
    account_type=AccountType.MARGIN,
    base_currency=USD,
    starting_balances=[Money(100_000, USD)],
)

engine.add_instrument(XAUUSD_SIM)
engine.add_data(bars)

# Default config: Buy Top 1SD, Sell Top 3SD (matches Notion analysis)
strategy_config = BBBStrategyConfig(
    instrument_id=XAUUSD_SIM.id,
    bar_type=bar_type,
    trade_size=Decimal("1"),
    buy_array_kind=ArrayKind.CLOSE,
    buy_band_kind=BandKind.TOP,
    buy_period=20,
    buy_sd=1.0,
    sell_array_kind=ArrayKind.CLOSE,
    sell_band_kind=BandKind.TOP,
    sell_period=20,
    sell_sd=3.0,
    frequency_bars=10,
    signal_variant=BBBSignalVariant.BASELINE,
)

strategy = BBBStrategy(config=strategy_config)
engine.add_strategy(strategy=strategy)

print("Running backtest...")
engine.run()
print("Backtest complete!")
```

**Cell 7 (code) — Results:**
```python
with pd.option_context("display.max_rows", 100, "display.max_columns", None, "display.width", 300):
    print("=== Account Report ===")
    print(engine.trader.generate_account_report(SIM))
    print("\n=== Positions Report ===")
    print(engine.trader.generate_positions_report())
    print("\n=== Order Fills Report ===")
    print(engine.trader.generate_order_fills_report())
```

**Cell 8 (code) — Cleanup:**
```python
engine.reset()
engine.dispose()
print(f"Results written to {CATALOG_PATH}")
```

- [ ] **Step 2: Verify notebook is valid JSON**

```bash
cd packages/runner && python3 -c "import json; json.load(open('runner/bbb_backtest.ipynb'))"
```

Expected: No error

- [ ] **Step 3: Commit**

```bash
git add packages/runner/runner/bbb_backtest.ipynb
git commit -m "feat: add BBB backtest Jupyter notebook with XAUUSD 5m bar config"
```

---

## Task 8: Exports and Final Integration

**Files:**
- Modify: `packages/runner/runner/strategies/__init__.py`
- Modify: `packages/runner/runner/__init__.py`

- [ ] **Step 1: Add exports to strategies __init__.py**

`packages/runner/runner/strategies/__init__.py`:
```python
from runner.strategies.bbb_strategy import (
    ArrayKind,
    BandKind,
    BBBSignalVariant,
    BBBStrategy,
    BBBStrategyConfig,
    MATrendKind,
)
from runner.strategies.ma_trend import TrendDirection

__all__ = [
    "ArrayKind",
    "BandKind",
    "BBBSignalVariant",
    "BBBStrategy",
    "BBBStrategyConfig",
    "MATrendKind",
    "TrendDirection",
]
```

- [ ] **Step 2: Run all tests one final time**

```bash
cd packages/runner && uv run pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add packages/runner/runner/strategies/__init__.py packages/runner/runner/__init__.py
git commit -m "feat: add public exports for BBB strategy module"
```
