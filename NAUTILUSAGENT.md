# NautilusTrader Advisor Agent

Reference document for NautilusTrader framework knowledge. Use this when building indicators, strategies, or integrating with the NautilusTrader ecosystem.

## Core Architecture

NautilusTrader is a high-performance algorithmic trading framework with a **Rust core** and **Python API**.

- **Performance layer**: Rust (via `nautilus_pyo3`) for core data types; Cython (`.pyx`/`.pxd`) for indicators and internal components; Python for user-facing API
- **Message Bus**: Central `MessageBus` orchestrates all communication. Data flows: Adapters -> DataEngine -> MessageBus -> Subscribed handlers (Actors/Strategies)
- **TradingNode**: Live deployment container; ingests data and events from multiple data/execution clients
- **Consistency guarantee**: Strategy code runs identically in backtest, sandbox, and live with zero code changes
- **Nanosecond timestamps**: All data carries `ts_event` (external event time) and `ts_init` (Nautilus creation time)
- **Identifiers**: `InstrumentId` = `Symbol.Venue` (e.g., `XAUUSD.IBCFD`)

## Indicators

### Base Class (`nautilus_trader.indicators.base.Indicator` -- Cython)

```python
# Properties
indicator.name: str           # Class name
indicator.has_inputs: bool    # True after first update
indicator.initialized: bool   # True when warmed up (enough data)

# Abstract methods (implement in subclass)
handle_bar(bar: Bar) -> None
handle_quote_tick(tick: QuoteTick) -> None
handle_trade_tick(tick: TradeTick) -> None
reset() -> None

# Internal
_set_has_inputs(setting: bool)
_set_initialized(setting: bool)
_reset()  # Abstract, implement in subclass
```

### `update_raw` Signatures (vary by indicator type)

- **Single value** (close): `update_raw(double value)` -- SMA, EMA, HMA, RSI, MACD, etc.
- **HLC** (high, low, close): `update_raw(double high, double low, double close)` -- ATR, BollingerBands, KeltnerChannel, Stochastics, CCI, IchimokuCloud, etc.
- **HL** (high, low): `update_raw(double high, double low)` -- DonchianChannel, AroonOscillator, DirectionalMovement
- **Special**: Swings uses `update_raw(double high, double low, datetime timestamp)`

### Built-in Indicators

- **Averages**: SMA, EMA, DEMA, WMA, HMA, AMA, WilderMA, VIDYA
- **Momentum**: RSI, ROC, CMO, Stochastics, CCI, EfficiencyRatio, RVI, PsychologicalLine
- **Trend**: MACD, AroonOscillator, DirectionalMovement, IchimokuCloud, LinearRegression, Bias, Swings, ArcherMAT
- **Volatility**: ATR, BollingerBands, DonchianChannel, KeltnerChannel, KeltnerPosition, VHF, VolatilityRatio
- **Volume**: OnBalanceVolume, Pressure, VWAP, KlingerVolumeOscillator
- **Other**: FuzzyCandlesticks, SpreadAnalyzer

### Output Patterns

- Single `value`: SMA, EMA, HMA, RSI, MACD, ATR, etc.
- Band outputs: `upper`, `middle`, `lower` -- BollingerBands, DonchianChannel, KeltnerChannel
- Stochastics: `value_k`, `value_d`
- AroonOscillator: `aroon_up`, `aroon_down`, `value`
- IchimokuCloud: `tenkan_sen`, `kijun_sen`, `senkou_span_a`, `senkou_span_b`, `chikou_span`

### Custom Indicator Pattern

Subclass `Indicator`, call `super().__init__([param1, param2, ...])`, implement `handle_bar`/`update_raw` and `_reset`. Set `self._set_has_inputs(True)` on first input, `self._set_initialized(True)` when warmed up.

NautilusTrader's `handle_bar` is the primary integration point. When registered via `register_indicator_for_bars`, the engine calls `handle_bar(bar)` automatically.

Collection-output indicators (e.g., `list[KeyLevel]`) are valid — the framework does not inspect or validate output properties. Scalar properties are conventional but not enforced.

## Strategies

### Lifecycle

1. `__init__(config)` -- Create indicators, store config. **Do NOT access `self.clock` or `self.logger` here**
2. `on_start()` -- Register indicators, subscribe to data, request historical data
3. `on_bar(bar)` / `on_quote_tick(tick)` / etc. -- Core trading logic
4. `on_stop()` -- Cancel orders, close positions, unsubscribe
5. `on_reset()` -- Reset indicators
6. `on_dispose()` -- Final cleanup

### Key APIs

```python
# Indicator registration (auto-updates indicator when bars arrive)
self.register_indicator_for_bars(bar_type, indicator)

# Data
self.request_bars(bar_type, start=...)  # Historical -> updates registered indicators
self.subscribe_bars(bar_type)           # Live -> on_bar() + registered indicators
self.subscribe_quote_ticks(instrument_id)
self.subscribe_trade_ticks(instrument_id)

# Check indicators
self.indicators_initialized()  # True when ALL registered indicators are initialized

# Orders
order = self.order_factory.market(instrument_id, OrderSide.BUY, quantity)
order = self.order_factory.limit(instrument_id, OrderSide.BUY, quantity, price)
self.submit_order(order)
self.cancel_order(order)
self.cancel_all_orders(instrument_id)
self.close_all_positions(instrument_id)

# Portfolio
self.portfolio.is_flat(instrument_id)
self.portfolio.is_net_long(instrument_id)
self.portfolio.unrealized_pnl(instrument_id)

# Cache
self.cache.instrument(instrument_id)
self.cache.bar_count(bar_type)
self.cache.positions_open(instrument_id=...)
```

### Config Pattern

Separate `StrategyConfig` (frozen msgspec model) from `Strategy` class. Config fields accessed via `self.config.field_name`. Use `order_id_tag` for multiple instances.

## Data System

### BarType String Format

`{instrument_id}-{step}-{aggregation}-{price_type}-{source}`

Example: `"XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL"`

### Aggregation Types

TICK, MINUTE, HOUR, DAY, WEEK, MONTH, YEAR, VOLUME, VALUE, RENKO, plus information-driven variants (TICK_IMBALANCE, TICK_RUNS, VOLUME_IMBALANCE, etc.)

### Data Types

- `Bar` (OHLCV): `bar.open`, `bar.high`, `bar.low`, `bar.close`, `bar.volume`, `bar.ts_event`, `bar.ts_init`
- `QuoteTick` (bid/ask)
- `TradeTick` (last trade)
- `OrderBookDelta` (L1/L2/L3)
- `OrderBookDepth10`

### ParquetDataCatalog

```python
catalog = ParquetDataCatalog(path)
catalog.instruments()                   # List all instruments
catalog.bars(bar_types=[...])           # Query bars
catalog.query(data_cls, ...)            # General query
catalog.write_data(data_list)           # Write data
```

## Backtesting

### High-level API (BacktestNode) -- preferred

```python
config = BacktestRunConfig(
    venues=[BacktestVenueConfig(name="SIM", oms_type="NETTING", ...)],
    data=[BacktestDataConfig(catalog_path=..., data_cls="...:Bar", instrument_id=...)],
    engine=BacktestEngineConfig(
        strategies=[ImportableStrategyConfig(strategy_path="...", config_path="...", config={...})],
        streaming=StreamingConfig(catalog_path=..., replace_existing=False),
    ),
)
node = BacktestNode(configs=[config])
results = node.run()
```

### Low-level API (BacktestEngine) -- for iteration

```python
engine = BacktestEngine()
engine.add_venue(...)
engine.add_instrument(instrument)
engine.add_data(bars)
engine.add_strategy(strategy)
engine.run()
engine.reset()  # Reuse with different strategy
```

## Interactive Brokers Adapter

- **Ports**: TWS paper=7497, live=7496; Gateway paper=4002, live=4001
- **Symbology**: Forex `EUR/USD.IDEALPRO`, Stocks `AAPL.SMART`, CFDs `IBUS30=CFD.IBCFD`
- **Critical**: IB CFDs have NO historical data via TWS API. For XAUUSD, use CMDTY (`XAUUSD=CMDTY.IBCMDTY`)
- **Pacing limits**: IB enforces rate limits; excessive requests can disable the API session

## Common Pitfalls

1. **Do not access `self.clock` or `self.logger` in Strategy `__init__`** -- not available until after registration
2. **Register indicators BEFORE requesting data** -- so historical bars warm up indicators
3. **Call `indicators_initialized()` before acting on indicator values** -- indicators return stale/zero values when not warmed up
4. **`update_raw` signatures are NOT uniform** -- each indicator has a specific signature
5. **IB CFDs have no historical data** -- use CMDTY for XAUUSD
6. **Bar timestamps**: `ts_init` should represent bar close time. Use `ts_init_delta` if bars are timestamped at open
7. **Fixed-point precision** -- use `instrument.make_qty()` and `instrument.make_price()` for orders
8. **Multiple `TradingNode` instances** in the same process are not supported

## Architectural Advice for This Project

### Where Custom Indicators Should Live

Custom indicators live in `packages/indicators/` (`nautilus-automatron-indicators`) — a standalone package with only `nautilus_trader` as a dependency. Both `nautilus_strategies` and `packages/server` add it as a dependency. This avoids coupling indicators to either the dashboard or specific strategies.

### Subclassing Indicator is Correct for Custom Indicators

- `register_indicator_for_bars` requires `Indicator` subclass
- `indicators_initialized()` only tracks `Indicator` subclasses
- Actor is wrong (independent lifecycle, message bus subscriptions)
- Standalone class is wrong (breaks registration, warmup tracking)

### Collection Output is Valid

The `Indicator` base class does not inspect output properties. A `.levels` property returning `list[KeyLevel]` is fine. Dual output (collection for strategies, scalar summaries for dashboard) is the recommended pattern.

### Strategy Usage Example

```python
from indicators.key_levels import KeyLevelIndicator
from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector

class SRStrategy(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.key_levels = KeyLevelIndicator(detectors=[
            SwingClusterDetector(period=5, cluster_distance=1.5),
        ])

    def on_start(self):
        self.register_indicator_for_bars(self.config.bar_type, self.key_levels)
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar):
        if not self.indicators_initialized():
            return
        support = self.key_levels.levels_below(float(bar.close))
        resistance = self.key_levels.levels_above(float(bar.close))
        # ... trading logic using levels
```
