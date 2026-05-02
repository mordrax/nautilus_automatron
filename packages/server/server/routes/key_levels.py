"""Routes for lifecycle-tracked key level data."""

from fastapi import APIRouter, Depends, HTTPException, Query

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store.key_levels import (
    DETECTOR_META,
    DETECTOR_REGISTRY,
    KeyLevelDto,
    compute_key_levels,
)


router = APIRouter()


@router.get("/key-levels/detectors")
def get_detectors() -> list[dict[str, str]]:
    """Return metadata for all registered key-level detectors (for picker UI)."""
    return DETECTOR_META


@router.get("/bars/{bar_type:path}/key-levels")
def get_key_levels_for_bar_type(
    bar_type: str,
    detectors: str = Query(..., description="Comma-separated detector IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[KeyLevelDto]:
    """Compute lifecycle-tracked key levels from catalog bars by bar type.

    Bar type identifies instrument + timeframe. Detectors are pure functions
    over the bar series and don't need a run ID.
    """
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    detector_ids = [d.strip() for d in detectors.split(",") if d.strip()]
    results: list[KeyLevelDto] = []
    for det_id in detector_ids:
        if det_id not in DETECTOR_REGISTRY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown detector: {det_id}",
            )
        results.extend(compute_key_levels(det_id, bars))

    return results
