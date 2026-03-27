"""Routes for technical indicator data."""

from fastapi import APIRouter, Depends, HTTPException, Query

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store.indicators import (
    IndicatorMeta,
    IndicatorResult,
    compute_indicator,
    list_available_indicators,
)

router = APIRouter()


@router.get("/indicators")
def get_available_indicators() -> list[IndicatorMeta]:
    return list_available_indicators()


@router.get("/bars/{bar_type:path}/indicators")
def get_indicators_for_bar_type(
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    """Compute indicators from catalog bars by bar type.

    Bar type identifies instrument + timeframe (e.g. XAUUSD.IBCFD-5-MINUTE-MID-EXTERNAL).
    Indicators are pure functions on bars — they don't need a run ID.
    """
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


# --- Deprecated endpoint ---
# The run-based indicator endpoint has been removed.
# Indicators are pure functions on bar type and don't need a run ID.
# Use GET /api/bars/{bar_type}/indicators?ids=... instead.
#
# @router.get("/runs/{run_id}/bars/{bar_type:path}/indicators")
# def get_indicators(run_id, bar_type, ids, catalog):
#     ...
