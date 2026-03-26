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
