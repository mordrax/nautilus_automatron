"""Routes for listing available strategies and bar types."""

from pathlib import Path

from fastapi import APIRouter, Depends

from runner.registry import STRATEGIES
from server.config import get_settings

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/strategies")
def list_strategies():
    """Return available strategies with their default params."""
    return [
        {
            "name": name,
            "label": info["label"],
            "default_params": info["default_params"],
        }
        for name, info in STRATEGIES.items()
    ]


@router.get("/bar-types")
def list_bar_types(store_path: Path = Depends(_store_path)):
    """Return available bar types from the data catalog."""
    data_bar_dir = store_path / "data" / "bar"
    if not data_bar_dir.exists():
        return []
    return sorted([d.name for d in data_bar_dir.iterdir() if d.is_dir()])
