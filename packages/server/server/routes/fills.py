"""Routes for order fills and computed trades."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import transforms
from server.store.catalog_reader import get_fills, read_backtest_data

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs/{run_id}/fills")
def get_fills_route(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    fills = get_fills(data)
    if not fills:
        raise HTTPException(status_code=404, detail="No fills found")
    return transforms.fills_to_dicts(fills)


@router.get("/runs/{run_id}/trades")
def get_trades(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    fills = get_fills(data)
    if not fills:
        raise HTTPException(status_code=404, detail="No fills found")
    fills_dicts = transforms.fills_to_dicts(fills)
    return transforms.fills_to_trades(fills_dicts)
