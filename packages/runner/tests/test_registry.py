import pytest

from runner.registry import STRATEGIES, get_strategy_info


def test_strategies_registry_has_ema_cross():
    assert "EMACross" in STRATEGIES
    assert STRATEGIES["EMACross"]["label"] == "EMA Crossover"


def test_get_strategy_info_returns_ema_cross():
    info = get_strategy_info("EMACross")
    assert info["strategy_path"] == "nautilus_trader.examples.strategies.ema_cross:EMACross"
    assert info["config_path"] == "nautilus_trader.examples.strategies.ema_cross:EMACrossConfig"
    assert "default_params" in info


def test_get_strategy_info_unknown_raises():
    with pytest.raises(KeyError):
        get_strategy_info("NonExistent")


def test_default_params_complete():
    info = get_strategy_info("EMACross")
    params = info["default_params"]
    assert params["trade_size"] == "1"
    assert params["fast_ema_period"] == 10
    assert params["slow_ema_period"] == 20
