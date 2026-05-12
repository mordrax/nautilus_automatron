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


class TestParseVenue:
    """Direct unit tests for the venue parser."""

    def test_single_dot_simple(self):
        from server.store.transforms import _parse_venue
        assert _parse_venue("XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL") == "IBCFD"

    def test_single_dot_with_slash_in_symbol(self):
        from server.store.transforms import _parse_venue
        assert _parse_venue("AUD/USD.SIM-100-TICK-MID-INTERNAL") == "SIM"

    def test_no_dot_returns_none(self):
        from server.store.transforms import _parse_venue
        assert _parse_venue("NOPE-1-MINUTE-BID-EXTERNAL") is None

    def test_multi_dot_takes_last_segment(self):
        from server.store.transforms import _parse_venue
        # Hypothetical multi-dot instrument id (a.b.c). Venue is the LAST dot segment.
        assert _parse_venue("AAA.BBB.CCC-1-MINUTE-MID-EXTERNAL") == "CCC"

    def test_dot_but_no_dash_after(self):
        from server.store.transforms import _parse_venue
        assert _parse_venue("SOMETHING.VENUEONLY") == "VENUEONLY"
