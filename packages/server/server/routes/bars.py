"""Routes for OHLCV bar data."""

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store import transforms
from server.store.catalog_reader import get_bars, list_bar_types_from_data, read_backtest_data

router = APIRouter()


@router.get("/runs/{run_id}/bars")
def list_bar_types(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    return list_bar_types_from_data(data)


@router.get("/runs/{run_id}/bars/{bar_type:path}")
def get_bars_route(run_id: str, bar_type: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    bars = get_bars(data, bar_type)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")
    return transforms.bars_to_ohlc(bars)
