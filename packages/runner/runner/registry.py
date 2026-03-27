"""Registry of available strategies for backtesting."""

STRATEGIES = {
    "BBBStrategy": {
        "label": "Bollinger Band Breakout",
        "strategy_path": "strategies.bbb_strategy:BBBStrategy",
        "config_path": "strategies.bbb_strategy:BBBStrategyConfig",
        "default_params": {
            "trade_size": "1",
            "buy_array_kind": "close",
            "buy_band_kind": "top",
            "buy_period": 20,
            "buy_sd": 2.0,
            "sell_array_kind": "close",
            "sell_band_kind": "top",
            "sell_period": 20,
            "sell_sd": 3.0,
            "frequency_bars": 10,
            "signal_variant": "baseline",
            "ma_trend_kind": "normal",
            "close_positions_on_stop": True,
        },
    },
}


def get_strategy_info(name: str) -> dict:
    """Get strategy registry entry. Raises KeyError if not found."""
    return STRATEGIES[name]
