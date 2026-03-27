"""Routes for raw instrument bar data from the data catalog."""

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store import transforms

router = APIRouter()


@router.get("/catalog/bars/{bar_type:path}")
def get_catalog_bars(bar_type: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    """Return OHLC data for a raw catalog bar type."""
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")
    return transforms.bars_to_ohlc(bars)


# --- Indicator endpoint removed ---
# Use GET /api/bars/{bar_type}/indicators?ids=... instead.
# Indicators are pure functions on bar type — a single endpoint serves both
# catalog bars and run bars (they are the same data).
