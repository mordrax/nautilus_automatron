"""Functions for reading backtest data via NautilusTrader's ParquetDataCatalog.

Provides typed filter functions over read_backtest() results, which returns
a mixed list of all data types from a backtest run.
"""

from nautilus_trader.model.data import Bar
from nautilus_trader.model.events.account import AccountState
from nautilus_trader.model.events.order import OrderFilled
from nautilus_trader.model.events.position import PositionClosed, PositionOpened
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def read_backtest_data(catalog: ParquetDataCatalog, run_id: str) -> list:
    """Read all data from a backtest run. Returns a mixed list of Nautilus objects."""
    return catalog.read_backtest(run_id)


def get_fills(data: list) -> list[OrderFilled]:
    """Filter backtest data to only OrderFilled events."""
    return [d for d in data if isinstance(d, OrderFilled)]


def get_positions_closed(data: list) -> list[PositionClosed]:
    """Filter backtest data to only PositionClosed events."""
    return [d for d in data if isinstance(d, PositionClosed)]


def get_positions_opened(data: list) -> list[PositionOpened]:
    """Filter backtest data to only PositionOpened events."""
    return [d for d in data if isinstance(d, PositionOpened)]


def get_account_states(data: list) -> list[AccountState]:
    """Filter backtest data to only AccountState events."""
    return [d for d in data if isinstance(d, AccountState)]


def get_bars(data: list, bar_type: str | None = None) -> list[Bar]:
    """Filter backtest data to only Bar objects, optionally by bar_type."""
    bars = [d for d in data if isinstance(d, Bar)]
    if bar_type:
        bars = [b for b in bars if str(b.bar_type) == bar_type]
    return bars


def list_bar_types_from_data(data: list) -> list[str]:
    """Extract sorted unique bar type strings from backtest data."""
    return sorted({str(b.bar_type) for b in data if isinstance(b, Bar)})
