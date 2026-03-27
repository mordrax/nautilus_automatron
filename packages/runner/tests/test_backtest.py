import pytest
import msgspec

from runner.backtest import build_run_config


def test_build_run_config_with_defaults():
    config = build_run_config(
        strategy_name="EMACross",
        bar_type="AUDUSD.SIM-100-TICK-MID-INTERNAL",
        catalog_path="/tmp/test_catalog",
    )
    assert len(config.venues) == 1
    assert config.venues[0].oms_type == "NETTING"
    assert config.venues[0].account_type == "MARGIN"
    assert config.venues[0].starting_balances == ["100000 USD"]

    assert len(config.data) == 1
    assert config.data[0].catalog_path == "/tmp/test_catalog"

    assert config.engine is not None
    assert len(config.engine.strategies) == 1
    assert config.engine.strategies[0].strategy_path == "nautilus_trader.examples.strategies.ema_cross:EMACross"
    assert config.engine.strategies[0].config["fast_ema_period"] == 10


def test_build_run_config_with_overrides():
    config = build_run_config(
        strategy_name="EMACross",
        bar_type="AUDUSD.SIM-100-TICK-MID-INTERNAL",
        catalog_path="/tmp/test_catalog",
        params={"fast_ema_period": 5, "slow_ema_period": 30},
    )
    strategy = config.engine.strategies[0]
    assert strategy.config["fast_ema_period"] == 5
    assert strategy.config["slow_ema_period"] == 30
    assert strategy.config["trade_size"] == "1"  # default preserved


def test_build_run_config_custom_balance():
    config = build_run_config(
        strategy_name="EMACross",
        bar_type="AUDUSD.SIM-100-TICK-MID-INTERNAL",
        catalog_path="/tmp/test_catalog",
        starting_balance="50000 USD",
    )
    assert config.venues[0].starting_balances == ["50000 USD"]


def test_build_run_config_unknown_strategy_raises():
    with pytest.raises(KeyError):
        build_run_config(
            strategy_name="NonExistent",
            bar_type="AUDUSD.SIM-100-TICK-MID-INTERNAL",
            catalog_path="/tmp/test_catalog",
        )


def test_run_config_is_serializable():
    """BacktestRunConfig should be serializable via msgspec for persistence."""
    from nautilus_trader.common.config import msgspec_encoding_hook

    config = build_run_config(
        strategy_name="EMACross",
        bar_type="AUDUSD.SIM-100-TICK-MID-INTERNAL",
        catalog_path="/tmp/test_catalog",
    )
    encoded = msgspec.json.encode(config, enc_hook=msgspec_encoding_hook)
    assert len(encoded) > 0
