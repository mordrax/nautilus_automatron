"""Tests for the /api/catalog route — provenance fields (venue, path, file_count)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.main import create_app


_BAR_TYPE_STR = "TEST.SIM-1-MINUTE-BID-EXTERNAL"


def _make_bar(ts_ns: int) -> Bar:
    return Bar(
        bar_type=BarType.from_str(_BAR_TYPE_STR),
        open=Price.from_str("1.00000"),
        high=Price.from_str("1.00010"),
        low=Price.from_str("0.99990"),
        close=Price.from_str("1.00005"),
        volume=Quantity.from_str("100.00"),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


@pytest.fixture
def store_with_bars(tmp_path: Path) -> Path:
    """Build a real on-disk catalog with one bar_type so the reader can scan it."""
    catalog = ParquetDataCatalog(path=str(tmp_path))
    catalog.write_data([
        _make_bar(1_704_067_200_000_000_000),  # 2024-01-01
        _make_bar(1_704_067_260_000_000_000),  # +60s
    ])
    return tmp_path


def test_catalog_route_includes_venue_path_file_count(
    store_with_bars: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("NAUTILUS_STORE_PATH", str(store_with_bars))
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    entry = body[0]

    assert entry["bar_type"] == _BAR_TYPE_STR
    assert entry["venue"] == "SIM"
    assert entry["path"].endswith("/data/bar/" + _BAR_TYPE_STR)
    assert entry["file_count"] >= 1


def test_catalog_entry_to_dict_venue_null_when_no_dot():
    """venue is null for a malformed bar_type with no '.' separator."""
    from server.store.transforms import catalog_entry_to_dict

    raw = {
        "instrument_id": "NODOTHERE",
        "bar_type": "NODOTHERE-1-MINUTE-BID-EXTERNAL",
        "bar_count": 1,
        "ts_min": 1_704_067_200_000_000_000,
        "ts_max": 1_704_067_200_000_000_000,
        "path": "/tmp/whatever",
        "file_count": 1,
    }
    out = catalog_entry_to_dict(raw)
    assert out["venue"] is None
