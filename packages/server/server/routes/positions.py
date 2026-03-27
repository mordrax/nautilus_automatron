"""Routes for position data."""

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store import transforms
from server.store.catalog_reader import get_positions_closed, read_backtest_data

router = APIRouter()


@router.get("/runs/{run_id}/positions")
def get_positions(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    positions = get_positions_closed(data)
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    return transforms.positions_closed_to_dicts(positions)
