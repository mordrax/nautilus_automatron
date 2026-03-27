import pytest

from runner.registry import STRATEGIES, get_strategy_info


def test_strategies_registry_has_bbb():
    assert "BBBStrategy" in STRATEGIES
    assert STRATEGIES["BBBStrategy"]["label"] == "Bollinger Band Breakout"


def test_get_strategy_info_returns_bbb():
    info = get_strategy_info("BBBStrategy")
    assert info["strategy_path"] == "strategies.bbb_strategy.BBBStrategy"
    assert info["config_path"] == "strategies.bbb_strategy.BBBStrategyConfig"
    assert "default_params" in info


def test_get_strategy_info_unknown_raises():
    with pytest.raises(KeyError):
        get_strategy_info("NonExistent")


def test_default_params_complete():
    info = get_strategy_info("BBBStrategy")
    params = info["default_params"]
    assert params["trade_size"] == "1"
    assert params["buy_sd"] == 2.0
    assert params["sell_sd"] == 3.0
    assert params["frequency_bars"] == 10
