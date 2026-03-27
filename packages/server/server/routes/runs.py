"""Routes for listing and viewing backtest runs."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import reader, transforms
from server.store.catalog_reader import (
    get_fills,
    get_positions_closed,
    get_positions_opened,
    list_bar_types_from_data,
    read_backtest_data,
)

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs")
def list_runs(
    page: int = 1,
    per_page: int = 20,
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    run_ids = catalog.list_backtest_runs()
    total = len(run_ids)

    start = (page - 1) * per_page
    end = start + per_page
    page_ids = run_ids[start:end]

    runs = []
    for run_id in page_ids:
        config = reader.read_run_config(store_path, run_id)
        data = read_backtest_data(catalog, run_id)

        fills = get_fills(data)
        positions_closed = get_positions_closed(data)
        positions_opened = get_positions_opened(data)

        summary = transforms.run_summary(
            run_id,
            config,
            len(positions_closed),
            len(fills),
            positions_opened,
            positions_closed,
        )
        runs.append(summary)

    return {"runs": runs, "total": total, "page": page, "per_page": per_page}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    config = reader.read_run_config(store_path, run_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    data = read_backtest_data(catalog, run_id)
    fills = get_fills(data)
    positions = get_positions_closed(data)

    return {
        "run_id": run_id,
        "config": config,
        "total_fills": len(fills),
        "total_positions": len(positions),
        "bar_types": list_bar_types_from_data(data),
    }
