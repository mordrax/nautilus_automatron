from decimal import Decimal

from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from runner.strategies.bbb_strategy import (
    ArrayKind,
    BandKind,
    BBBSignalVariant,
    BBBStrategyConfig,
    MATrendKind,
    is_cross_above,
    is_cross_below,
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


def test_cross_above_detected():
    prices = [100.0, 98.0, 102.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_above(prices, bands, 2) is True


def test_cross_above_not_detected_when_already_above():
    prices = [100.0, 101.0, 102.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_above(prices, bands, 2) is False


def test_cross_below_detected():
    prices = [100.0, 102.0, 98.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_below(prices, bands, 2) is True


def test_cross_below_not_detected_when_already_below():
    prices = [100.0, 98.0, 97.0]
    bands = [100.0, 100.0, 100.0]
    assert is_cross_below(prices, bands, 2) is False


def test_cross_above_at_boundary():
    prices = [99.0, 100.0]
    bands = [100.0, 100.0]
    assert is_cross_above(prices, bands, 1) is True


from runner.strategies.bbb_strategy import BBBStrategy


def make_config(**overrides):
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


def test_strategy_breakout_config():
    config = make_config(
        signal_variant=BBBSignalVariant.BREAKOUT,
        ma_trend_kind=MATrendKind.NORMAL,
    )
    strategy = BBBStrategy(config=config)
    assert strategy.config.signal_variant == BBBSignalVariant.BREAKOUT
    assert strategy.config.ma_trend_kind == MATrendKind.NORMAL
    assert strategy._ema_normal_history == []
