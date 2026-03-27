"""Routes for listing available instrument data in the catalog."""

from pathlib import Path

from fastapi import APIRouter, Depends

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog, _store_path
from server.store import reader, transforms

router = APIRouter()


@router.get("/catalog")
def list_catalog(
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    entries = reader.list_catalog_entries(store_path, catalog=catalog)
    return [transforms.catalog_entry_to_dict(e) for e in entries]
