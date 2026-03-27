"""Registry of available strategies for backtesting.

Ships with NautilusTrader's built-in EMACross strategy.
Additional strategies can be added via strategies_local.py (gitignored).
"""

STRATEGIES: dict[str, dict] = {
    "EMACross": {
        "label": "EMA Crossover",
        "strategy_path": "nautilus_trader.examples.strategies.ema_cross:EMACross",
        "config_path": "nautilus_trader.examples.strategies.ema_cross:EMACrossConfig",
        "default_params": {
            "trade_size": "1",
            "fast_ema_period": 10,
            "slow_ema_period": 20,
            "close_positions_on_stop": True,
        },
    },
}

# Load additional strategies from local (gitignored) config
try:
    from runner.strategies_local import STRATEGIES as _LOCAL

    STRATEGIES.update(_LOCAL)
except ImportError:
    pass


def get_strategy_info(name: str) -> dict:
    """Get strategy registry entry. Raises KeyError if not found."""
    return STRATEGIES[name]
