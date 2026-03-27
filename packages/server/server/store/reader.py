"""Pure functions for reading NautilusTrader backtest catalog data.

The catalog uses Arrow IPC stream format (.feather files) organized as:
  backtest_catalog/backtest/{run_id}/
    config.json
    order_filled_0.feather      (Arrow IPC stream)
    position_opened_0.feather
    position_closed_0.feather
    account_state_0.feather
    bar/{bar_type}/{instrument}_*.feather
"""

import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc


def list_run_ids(store_path: Path) -> list[str]:
    """List all backtest run IDs in the store."""
    backtest_dir = store_path / "backtest"
    if not backtest_dir.exists():
        return []
    return sorted(
        [d.name for d in backtest_dir.iterdir() if d.is_dir()],
        reverse=True,
    )


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


def read_fills(store_path: Path, run_id: str) -> pa.Table | None:
    """Read order_filled events for a run."""
    return _read_ipc_stream(
        store_path / "backtest" / run_id / "order_filled_0.feather"
    )


def read_positions_opened(store_path: Path, run_id: str) -> pa.Table | None:
    """Read position_opened events for a run."""
    return _read_ipc_stream(
        store_path / "backtest" / run_id / "position_opened_0.feather"
    )


def read_positions_closed(store_path: Path, run_id: str) -> pa.Table | None:
    """Read position_closed events for a run."""
    return _read_ipc_stream(
        store_path / "backtest" / run_id / "position_closed_0.feather"
    )


def read_account_states(store_path: Path, run_id: str) -> pa.Table | None:
    """Read account_state events for a run."""
    return _read_ipc_stream(
        store_path / "backtest" / run_id / "account_state_0.feather"
    )


def list_bar_types(store_path: Path, run_id: str) -> list[str]:
    """List available bar types for a run."""
    bar_dir = store_path / "backtest" / run_id / "bar"
    if not bar_dir.exists():
        return []
    return sorted([d.name for d in bar_dir.iterdir() if d.is_dir()])


def read_bars_raw(store_path: Path, run_id: str, bar_type: str) -> pa.Table | None:
    """Read raw bar data (fixed-point encoded) for a bar type.

    Returns the raw Arrow table — caller must decode fixed-point columns
    using nautilus_trader.serialization.arrow.serializer.ArrowSerializer.
    """
    bar_dir = store_path / "backtest" / run_id / "bar" / bar_type
    if not bar_dir.exists():
        return None

    tables = []
    for feather_file in sorted(bar_dir.glob("*.feather")):
        table = _read_ipc_stream(feather_file)
        if table is not None:
            tables.append(table)

    if not tables:
        return None

    return pa.concat_tables(tables) if len(tables) > 1 else tables[0]


def list_catalog_entries(store_path: Path) -> list[dict]:
    """Scan all runs to build a deduplicated catalog of available instrument data.

    For each unique bar_type directory across all runs, reads all feather files
    to extract instrument ID, total bar count, and date range.
    Returns one entry per unique bar_type.
    """
    seen: dict[str, dict] = {}

    for run_id in list_run_ids(store_path):
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


def delete_run(store_path: Path, run_id: str) -> bool:
    """Delete a backtest run directory. Returns True if deleted."""
    run_dir = store_path / "backtest" / run_id
    if not run_dir.exists():
        return False
    shutil.rmtree(run_dir)
    return True
