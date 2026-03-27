"""Shared FastAPI dependency functions for route handlers."""

from pathlib import Path

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings


def _store_path() -> Path:
    return Path(get_settings().store_path)


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))
