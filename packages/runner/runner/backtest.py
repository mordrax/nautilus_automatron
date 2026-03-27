"""Backtest execution using NautilusTrader's BacktestNode.

Usage from notebook:
    config = build_run_config("BBBStrategy", "XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL", catalog_path, params={...})
    result = run_backtest(config)

Usage from server:
    Same — build config from API request, call run_backtest().
"""

from pathlib import Path

import msgspec
from nautilus_trader.backtest.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
)
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.results import BacktestResult
from nautilus_trader.config import LoggingConfig
from nautilus_trader.persistence.config import StreamingConfig
from nautilus_trader.trading.config import ImportableStrategyConfig

from nautilus_trader.persistence.catalog import ParquetDataCatalog

from runner.registry import get_strategy_info


def _resolve_bar_type(bar_type_dir_name: str, catalog_path: str) -> str:
    """Resolve the actual NautilusTrader bar type string from a catalog directory name.

    The catalog directory name may differ from the actual bar type string when
    instrument IDs contain slashes (e.g. 'AUD/USD.SIM' → dir 'AUDUSD.SIM').
    We load a sample bar to get the canonical bar type string.
    """
    catalog = ParquetDataCatalog(catalog_path)
    bars = catalog.bars(bar_types=[bar_type_dir_name], as_nautilus=True)
    if bars:
        return str(bars[0].bar_type)
    return bar_type_dir_name


def build_run_config(
    strategy_name: str,
    bar_type: str,
    catalog_path: str,
    params: dict | None = None,
    starting_balance: str = "100000 USD",
    log_level: str = "WARNING",
) -> BacktestRunConfig:
    """Build a complete BacktestRunConfig from user inputs.

    Args:
        strategy_name: Registry key, e.g. "BBBStrategy".
        bar_type: Full bar type string or catalog directory name,
                  e.g. "XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL".
        catalog_path: Path to the data catalog (reads data/ for bars, writes backtest/ for results).
        params: Strategy parameter overrides (merged over defaults).
        starting_balance: Starting balance string, e.g. "100000 USD".
        log_level: NautilusTrader log level.

    Returns:
        A fully configured BacktestRunConfig ready for BacktestNode.
    """
    info = get_strategy_info(strategy_name)

    # Merge user params over defaults
    merged_params = {**info["default_params"], **(params or {})}

    # Resolve the canonical bar type string from the catalog (handles slash/no-slash mismatch)
    resolved_bar_type = _resolve_bar_type(bar_type, catalog_path)

    # Parse instrument_id from bar_type
    # e.g. "XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL" → instrument "XAUUSD.IBCFD"
    instrument_id = resolved_bar_type.split("-")[0]  # e.g. "XAUUSD.IBCFD" or "AUD/USD.SIM"

    # Add instrument_id and bar_type to strategy params (required by BBBStrategyConfig)
    merged_params["instrument_id"] = instrument_id
    merged_params["bar_type"] = resolved_bar_type

    strategy_config = ImportableStrategyConfig(
        strategy_path=info["strategy_path"],
        config_path=info["config_path"],
        config=merged_params,
    )

    venue_config = BacktestVenueConfig(
        name="SIM",
        oms_type="NETTING",
        account_type="MARGIN",
        starting_balances=[starting_balance],
    )

    data_config = BacktestDataConfig(
        catalog_path=catalog_path,
        data_cls="nautilus_trader.model.data:Bar",
        instrument_id=instrument_id,
    )

    engine_config = BacktestEngineConfig(
        strategies=[strategy_config],
        logging=LoggingConfig(log_level=log_level),
        streaming=StreamingConfig(
            catalog_path=catalog_path,
            replace_existing=False,
        ),
    )

    return BacktestRunConfig(
        venues=[venue_config],
        data=[data_config],
        engine=engine_config,
    )


def run_backtest(config: BacktestRunConfig) -> BacktestResult:
    """Execute a backtest using NautilusTrader's BacktestNode.

    Args:
        config: A BacktestRunConfig (built via build_run_config or loaded from JSON).

    Returns:
        BacktestResult with stats, P&L, run metadata.
    """
    node = BacktestNode(configs=[config])
    results = node.run()
    if not results:
        raise RuntimeError(
            "BacktestNode returned no results — the backtest may have failed silently. "
            "Check that the instrument is registered and bar data is available."
        )
    return results[0]


def save_run_config(config: BacktestRunConfig, catalog_path: str, run_id: str) -> None:
    """Save the BacktestRunConfig alongside the run's config.json for reproducibility.

    Writes a run_config.json file next to the engine's config.json.
    This file contains everything needed to rerun the backtest.
    """
    from nautilus_trader.common.config import msgspec_encoding_hook

    run_dir = Path(catalog_path) / "backtest" / run_id
    if not run_dir.exists():
        return

    config_bytes = msgspec.json.encode(config, enc_hook=msgspec_encoding_hook)
    config_path = run_dir / "run_config.json"
    config_path.write_bytes(config_bytes)


def load_run_config(catalog_path: str, run_id: str) -> BacktestRunConfig | None:
    """Load a saved BacktestRunConfig from a run directory."""
    from nautilus_trader.common.config import msgspec_decoding_hook

    config_path = Path(catalog_path) / "backtest" / run_id / "run_config.json"
    if not config_path.exists():
        return None

    return msgspec.json.decode(
        config_path.read_bytes(),
        type=BacktestRunConfig,
        dec_hook=msgspec_decoding_hook,
    )
