"""Routes for listing available instrument data in the catalog."""

from pathlib import Path

from fastapi import APIRouter, Depends

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/catalog")
def list_catalog(store_path: Path = Depends(_store_path)):
    entries = reader.list_catalog_entries(store_path)
    return [transforms.catalog_entry_to_dict(e) for e in entries]
