"""Routes for raw instrument bar data from the data catalog."""

from fastapi import APIRouter, Depends, HTTPException, Query

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store import transforms
from server.store.indicators import IndicatorResult, compute_indicator

router = APIRouter()


@router.get("/catalog/bars/{bar_type:path}/indicators")
def get_catalog_indicators(
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    """Compute indicators on raw catalog bar data."""
    bars = catalog.bars(bar_types=[bar_type])
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


@router.get("/catalog/bars/{bar_type:path}")
def get_catalog_bars(bar_type: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    """Return OHLC data for a raw catalog bar type."""
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")
    return transforms.bars_to_ohlc(bars)
