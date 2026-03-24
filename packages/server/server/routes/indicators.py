"""Routes for technical indicator data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from server.config import get_settings
from server.store import reader
from server.store.indicators import compute_indicator, list_available_indicators

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/indicators")
def get_available_indicators():
    return list_available_indicators()


@router.get("/runs/{run_id}/bars/{bar_type}/indicators")
def get_indicators(
    run_id: str,
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    store_path: Path = Depends(_store_path),
):
    raw_table = reader.read_bars_raw(store_path, run_id, bar_type)
    if raw_table is None:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    from nautilus_trader.model.data import Bar
    from nautilus_trader.serialization.arrow.serializer import ArrowSerializer

    bars = ArrowSerializer.deserialize(Bar, raw_table)

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

    return results
