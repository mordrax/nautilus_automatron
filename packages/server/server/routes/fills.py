"""Routes for order fills and computed trades."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/runs/{run_id}/fills")
def get_fills(run_id: str, store_path: Path = Depends(_store_path)):
    table = reader.read_fills(store_path, run_id)
    if table is None:
        raise HTTPException(status_code=404, detail="No fills found")
    return transforms.fills_table_to_dicts(table)


@router.get("/runs/{run_id}/trades")
def get_trades(run_id: str, store_path: Path = Depends(_store_path)):
    table = reader.read_fills(store_path, run_id)
    if table is None:
        raise HTTPException(status_code=404, detail="No fills found")
    fills = transforms.fills_table_to_dicts(table)
    return transforms.fills_to_trades(fills)
