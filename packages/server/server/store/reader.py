"""Pure functions for reading NautilusTrader backtest catalog data.

Provides:
  - read_run_config: read config.json for a specific run
  - list_catalog_entries: scan data catalog to build a list of available instrument bar data
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def read_run_config(store_path: Path, run_id: str) -> dict:
    """Read the config.json for a specific run."""
    config_path = store_path / "backtest" / run_id / "config.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def list_catalog_entries(
    store_path: Path,
    catalog: ParquetDataCatalog | None = None,
) -> list[dict]:
    """Scan the data catalog to build a list of available instrument bar data.

    Reads bar type directories from data/bar/ and extracts instrument ID,
    total bar count, and date range for each.
    Returns one entry per unique bar_type.
    """
    if catalog is None:
        return []

    data_bar_dir = store_path / "data" / "bar"
    if not data_bar_dir.exists():
        return []

    entries: list[dict] = []

    for bar_type_dir in sorted(data_bar_dir.iterdir()):
        if not bar_type_dir.is_dir():
            continue

        bar_type_name = bar_type_dir.name
        bars = catalog.bars(bar_types=[bar_type_name])

        if not bars:
            continue

        instrument_id = str(bars[0].bar_type.instrument_id)
        # The on-disk directory strips characters like '/' from FX pairs,
        # so the runtime BarType string is the source of truth for matching
        # against bar_types reported elsewhere (e.g. run_detail.bar_types).
        bar_type_str = str(bars[0].bar_type)
        ts_min = min(b.ts_event for b in bars)
        ts_max = max(b.ts_event for b in bars)

        entries.append({
            "instrument_id": instrument_id,
            "bar_type": bar_type_str,
            "bar_count": len(bars),
            "ts_min": ts_min,
            "ts_max": ts_max,
            "path": str(bar_type_dir.resolve()),
            "file_count": sum(1 for _ in bar_type_dir.glob("*.parquet")),
        })

    return entries


def delete_run(store_path: Path, run_id: str) -> bool:
    """Delete a backtest run directory. Returns True if deleted."""
    run_dir = store_path / "backtest" / run_id
    if not run_dir.exists():
        return False
    shutil.rmtree(run_dir)
    return True
