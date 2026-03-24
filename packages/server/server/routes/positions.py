"""Routes for position data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/runs/{run_id}/positions")
def get_positions(run_id: str, store_path: Path = Depends(_store_path)):
    table = reader.read_positions_closed(store_path, run_id)
    if table is None:
        raise HTTPException(status_code=404, detail="No positions found")
    return transforms.positions_closed_to_dicts(table)
