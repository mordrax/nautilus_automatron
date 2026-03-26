from decimal import Decimal
from enum import Enum

from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import PositiveFloat, PositiveInt, StrategyConfig
from nautilus_trader.indicators import BollingerBands
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


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
    buy_array_kind: ArrayKind = ArrayKind.CLOSE
    buy_band_kind: BandKind = BandKind.TOP
    buy_period: PositiveInt = 20
    buy_sd: PositiveFloat = 2.0
    sell_array_kind: ArrayKind = ArrayKind.CLOSE
    sell_band_kind: BandKind = BandKind.TOP
    sell_period: PositiveInt = 20
    sell_sd: PositiveFloat = 2.0
    frequency_bars: PositiveInt = 10
    signal_variant: BBBSignalVariant = BBBSignalVariant.BASELINE
    ma_trend_kind: MATrendKind = MATrendKind.NORMAL
    close_positions_on_stop: bool = True


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
        self.buy_bb = BollingerBands(config.buy_period, config.buy_sd)
        self.sell_bb = BollingerBands(config.sell_period, config.sell_sd)
        self._prev_buy_price: float | None = None
        self._prev_buy_band: float | None = None
        self._prev_sell_price: float | None = None
        self._prev_sell_band: float | None = None
        self._prev_close: float | None = None
        self._prev_high: float | None = None
        self._prev_low: float | None = None
        self._bars_since_entry: int = 0
        self._has_position: bool = False
        self._close_history: list[float] = []

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

        self._close_history.append(bar.close.as_double())

        self._prev_buy_price = buy_price
        self._prev_buy_band = buy_band
        self._prev_sell_price = sell_price
        self._prev_sell_band = sell_band
        self._prev_close = bar.close.as_double()
        self._prev_high = bar.high.as_double()
        self._prev_low = bar.low.as_double()

    def _get_ma_trend(self) -> "TrendDirection":
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

    def _check_signals(self, buy_price, buy_band, sell_price, sell_band) -> None:
        is_long = self.portfolio.is_net_long(self.config.instrument_id)

        # Exit check first (always check, no frequency limit)
        if is_long:
            is_exit = (
                self._prev_sell_price > self._prev_sell_band
                and sell_price <= sell_band
            )

            # Breakout mode: also exit on MA trend down
            if self.config.signal_variant == BBBSignalVariant.BREAKOUT:
                from runner.strategies.ma_trend import TrendDirection
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
                from runner.strategies.ma_trend import TrendDirection
                ma_trend = self._get_ma_trend()
                if ma_trend != TrendDirection.UP:
                    is_entry = False

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
        self._close_history = []
