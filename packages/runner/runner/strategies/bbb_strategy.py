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
