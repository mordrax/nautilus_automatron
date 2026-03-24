"""Routes for OHLCV bar data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/runs/{run_id}/bars")
def list_bar_types(run_id: str, store_path: Path = Depends(_store_path)):
    return reader.list_bar_types(store_path, run_id)


@router.get("/runs/{run_id}/bars/{bar_type}")
def get_bars(run_id: str, bar_type: str, store_path: Path = Depends(_store_path)):
    raw_table = reader.read_bars_raw(store_path, run_id, bar_type)
    if raw_table is None:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    # Use Nautilus deserializer to decode fixed-point bar prices
    from nautilus_trader.model.data import Bar
    from nautilus_trader.serialization.arrow.serializer import ArrowSerializer

    bars = ArrowSerializer.deserialize(Bar, raw_table)
    return transforms.bars_to_ohlc(bars)
