"""Routes for technical indicator data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store.catalog_reader import get_bars, read_backtest_data
from server.store.indicators import (
    IndicatorMeta,
    IndicatorResult,
    compute_indicator,
    list_available_indicators,
)

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/indicators")
def get_available_indicators() -> list[IndicatorMeta]:
    return list_available_indicators()


@router.get("/runs/{run_id}/bars/{bar_type}/indicators")
def get_indicators(
    run_id: str,
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    data = read_backtest_data(catalog, run_id)
    bars = get_bars(data, bar_type)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    indicator_ids = [i.strip() for i in ids.split(",") if i.strip()]
    results = []
    for indicator_id in indicator_ids:
        try:
            results.append(compute_indicator(indicator_id, bars))
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown indicator: {indicator_id}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error computing {indicator_id}: {str(e)}",
            )

    return results
