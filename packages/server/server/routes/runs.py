"""Routes for listing and viewing backtest runs."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog, _store_path
from server.store import reader, transforms
from server.store.catalog_reader import (
    get_fills,
    get_positions_closed,
    get_positions_opened,
    list_bar_types_from_data,
    read_backtest_data,
)

router = APIRouter()


class CreateBacktestRequest(BaseModel):
    strategy: str
    bar_type: str
    params: dict | None = None
    starting_balance: int = 100_000


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


@router.post("/runs")
def create_run(
    request: CreateBacktestRequest,
    store_path: Path = Depends(_store_path),
):
    """Create and execute a new backtest."""
    from runner.backtest import build_run_config, run_backtest, save_run_config
    try:
        config = build_run_config(
            strategy_name=request.strategy,
            bar_type=request.bar_type,
            catalog_path=str(store_path),
            params=request.params,
            starting_balance=f"{request.starting_balance} USD",
        )
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy}")

    result = run_backtest(config)

    # Save the run config for future reruns
    save_run_config(config, str(store_path), result.instance_id)

    return {"run_id": result.instance_id, "status": "completed"}


@router.post("/runs/{run_id}/rerun")
def rerun(run_id: str, store_path: Path = Depends(_store_path)):
    """Rerun a backtest using its saved BacktestRunConfig."""
    from runner.backtest import load_run_config, run_backtest, save_run_config
    config = load_run_config(str(store_path), run_id)
    if config is None:
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} has no saved run_config.json — cannot rerun",
        )

    result = run_backtest(config)
    save_run_config(config, str(store_path), result.instance_id)

    return {"run_id": result.instance_id, "status": "completed"}


@router.delete("/runs/{run_id}")
def delete_run_endpoint(run_id: str, store_path: Path = Depends(_store_path)):
    """Delete a backtest run from the catalog."""
    deleted = reader.delete_run(store_path, run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"status": "deleted", "run_id": run_id}
