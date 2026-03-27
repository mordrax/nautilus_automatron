"""Pure functions for reading NautilusTrader backtest catalog data.

Provides:
  - read_run_config: read config.json for a specific run
  - list_catalog_entries: scan all runs to build a deduplicated catalog of bar data
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.compute as pc

if TYPE_CHECKING:
    from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def read_run_config(store_path: Path, run_id: str) -> dict:
    """Read the config.json for a specific run."""
    config_path = store_path / "backtest" / run_id / "config.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def _read_ipc_stream(path: Path) -> pa.Table | None:
    """Read an Arrow IPC stream file, returning None if empty or missing."""
    if not path.exists():
        return None
    try:
        reader = pa.ipc.open_stream(path)
        table = reader.read_all()
        return table if len(table) > 0 else None
    except (pa.ArrowInvalid, pa.ArrowIOError):
        return None


def list_catalog_entries(
    store_path: Path,
    catalog: ParquetDataCatalog | None = None,
) -> list[dict]:
    """Scan all runs to build a deduplicated catalog of available instrument data.

    For each unique bar_type directory across all runs, reads all feather files
    to extract instrument ID, total bar count, and date range.
    Returns one entry per unique bar_type.
    """
    if catalog is not None:
        run_ids = catalog.list_backtest_runs()
    else:
        # Fallback: scan directories directly
        backtest_dir = store_path / "backtest"
        if not backtest_dir.exists():
            run_ids = []
        else:
            run_ids = sorted(
                [d.name for d in backtest_dir.iterdir() if d.is_dir()],
                reverse=True,
            )

    seen: dict[str, dict] = {}

    for run_id in run_ids:
        bar_dir = store_path / "backtest" / run_id / "bar"
        if not bar_dir.exists():
            continue

        for bar_type_dir in sorted(bar_dir.iterdir()):
            if not bar_type_dir.is_dir():
                continue

            bar_type_name = bar_type_dir.name
            if bar_type_name in seen:
                continue

            total_bars = 0
            ts_min: int | None = None
            ts_max: int | None = None
            instrument_id = ""
            bar_type_str = ""

            for feather_file in sorted(bar_type_dir.glob("*.feather")):
                table = _read_ipc_stream(feather_file)
                if table is None:
                    continue

                total_bars += len(table)

                if not instrument_id:
                    metadata = table.schema.metadata or {}
                    instrument_id = metadata.get(b"instrument_id", b"").decode()
                    bar_type_str = metadata.get(b"bar_type", b"").decode()

                ts_init = table.column("ts_init")
                file_min = pc.min(ts_init).as_py()
                file_max = pc.max(ts_init).as_py()

                if ts_min is None or file_min < ts_min:
                    ts_min = file_min
                if ts_max is None or file_max > ts_max:
                    ts_max = file_max

            if total_bars > 0:
                seen[bar_type_name] = {
                    "instrument_id": instrument_id,
                    "bar_type": bar_type_str or bar_type_name,
                    "bar_count": total_bars,
                    "ts_min": ts_min,
                    "ts_max": ts_max,
                }

    return list(seen.values())
