"""Routes for listing and viewing backtest runs."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/runs")
def list_runs(
    page: int = 1,
    per_page: int = 20,
    store_path: Path = Depends(_store_path),
):
    run_ids = reader.list_run_ids(store_path)
    total = len(run_ids)

    start = (page - 1) * per_page
    end = start + per_page
    page_ids = run_ids[start:end]

    runs = []
    for run_id in page_ids:
        config = reader.read_run_config(store_path, run_id)
        fills_table = reader.read_fills(store_path, run_id)
        positions_table = reader.read_positions_closed(store_path, run_id)
        positions_opened = reader.read_positions_opened(store_path, run_id)

        fills_count = len(fills_table) if fills_table is not None else 0
        positions_count = len(positions_table) if positions_table is not None else 0

        summary = transforms.run_summary(
            run_id, config, positions_count, fills_count, positions_opened
        )
        runs.append(summary)

    return {"runs": runs, "total": total, "page": page, "per_page": per_page}


@router.get("/runs/{run_id}")
def get_run(run_id: str, store_path: Path = Depends(_store_path)):
    config = reader.read_run_config(store_path, run_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    fills_table = reader.read_fills(store_path, run_id)
    positions_table = reader.read_positions_closed(store_path, run_id)

    return {
        "run_id": run_id,
        "config": config,
        "total_fills": len(fills_table) if fills_table is not None else 0,
        "total_positions": len(positions_table) if positions_table is not None else 0,
        "bar_types": reader.list_bar_types(store_path, run_id),
    }
