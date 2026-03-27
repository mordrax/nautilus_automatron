"""Routes for account state and equity curve."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import transforms
from server.store.catalog_reader import get_account_states, read_backtest_data

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs/{run_id}/account")
def get_account(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    states = get_account_states(data)
    if not states:
        raise HTTPException(status_code=404, detail="No account data found")
    return transforms.account_states_to_dicts(states)


@router.get("/runs/{run_id}/equity")
def get_equity(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    states = get_account_states(data)
    if not states:
        raise HTTPException(status_code=404, detail="No account data found")
    account_dicts = transforms.account_states_to_dicts(states)
    return transforms.account_states_to_equity(account_dicts)
