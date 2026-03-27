import pytest
import msgspec

from runner.backtest import build_run_config


def test_build_run_config_with_defaults():
    config = build_run_config(
        strategy_name="BBBStrategy",
        bar_type="XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL",
        catalog_path="/tmp/test_catalog",
    )
    assert len(config.venues) == 1
    assert config.venues[0].name == "SIM"
    assert config.venues[0].oms_type == "NETTING"
    assert config.venues[0].account_type == "MARGIN"
    assert config.venues[0].starting_balances == ["100000 USD"]

    assert len(config.data) == 1
    assert config.data[0].catalog_path == "/tmp/test_catalog"

    assert config.engine is not None
    assert len(config.engine.strategies) == 1
    assert config.engine.strategies[0].strategy_path == "strategies.bbb_strategy.BBBStrategy"
    assert config.engine.strategies[0].config["buy_sd"] == 2.0


def test_build_run_config_with_overrides():
    config = build_run_config(
        strategy_name="BBBStrategy",
        bar_type="XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL",
        catalog_path="/tmp/test_catalog",
        params={"buy_sd": 1.5, "sell_sd": 4.0},
    )
    strategy = config.engine.strategies[0]
    assert strategy.config["buy_sd"] == 1.5
    assert strategy.config["sell_sd"] == 4.0
    assert strategy.config["buy_period"] == 20  # default preserved


def test_build_run_config_custom_balance():
    config = build_run_config(
        strategy_name="BBBStrategy",
        bar_type="XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL",
        catalog_path="/tmp/test_catalog",
        starting_balance="50000 USD",
    )
    assert config.venues[0].starting_balances == ["50000 USD"]


def test_build_run_config_unknown_strategy_raises():
    with pytest.raises(KeyError):
        build_run_config(
            strategy_name="NonExistent",
            bar_type="XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL",
            catalog_path="/tmp/test_catalog",
        )


def test_run_config_is_serializable():
    """BacktestRunConfig should be serializable via msgspec for persistence."""
    from nautilus_trader.common.config import msgspec_encoding_hook

    config = build_run_config(
        strategy_name="BBBStrategy",
        bar_type="XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL",
        catalog_path="/tmp/test_catalog",
    )
    # Should not raise
    encoded = msgspec.json.encode(config, enc_hook=msgspec_encoding_hook)
    assert len(encoded) > 0
