"""Tests for the /api/bars/{bar_type}/key-levels and /api/key-levels/detectors routes.

The catalog dependency is overridden with a stub that returns pre-built bars,
so these tests don't need a real ParquetDataCatalog on disk.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.objects import Price, Quantity

from server.main import create_app
from server.routes.dependencies import _catalog


# ---------------------------------------------------------------------------
# Bar factory — duplicated from packages/indicators/tests/helpers/bar_factory.py
# (intentional copy to keep server tests independent of indicators test helpers).
# ---------------------------------------------------------------------------

_DEFAULT_BAR_TYPE_STR = "TEST.SIM-1-MINUTE-BID-EXTERNAL"
_DEFAULT_BAR_TYPE = BarType.from_str(_DEFAULT_BAR_TYPE_STR)
_1H_NS = 3_600_000_000_000
_BASE_TS = 1_704_067_200_000_000_000  # 2024-01-01 00:00:00 UTC


def _make_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    ts_ns: int,
    bar_type: BarType = _DEFAULT_BAR_TYPE,
) -> Bar:
    return Bar(
        bar_type=bar_type,
        open=Price.from_str(f"{open_:.5f}"),
        high=Price.from_str(f"{high:.5f}"),
        low=Price.from_str(f"{low:.5f}"),
        close=Price.from_str(f"{close:.5f}"),
        volume=Quantity.from_str("100.00"),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


def _make_equal_highs_lows_bars() -> list[Bar]:
    """Bars with repeating swing highs near 110 and lows near 90.

    Mirrors the fixture in test_equal_highs_lows.py — produces at least one
    confirmed level for both highs and lows.
    """
    data = [
        (100.0, 102.0, 98.0, 101.0),
        (101.0, 106.0, 100.0, 105.0),
        (105.0, 110.0, 104.0, 108.0),
        (108.0, 108.0, 100.0, 102.0),
        (102.0, 103.0, 95.0, 96.0),
        (96.0, 97.0, 92.0, 93.0),
        (93.0, 94.0, 90.0, 91.0),
        (91.0, 96.0, 91.0, 95.0),
        (95.0, 100.0, 94.0, 99.0),
        (99.0, 104.0, 98.0, 103.0),
        (103.0, 109.0, 102.0, 107.0),
        (107.0, 107.0, 99.0, 101.0),
        (101.0, 102.0, 95.0, 97.0),
        (97.0, 98.0, 93.0, 94.0),
        (94.0, 95.0, 91.0, 92.0),
        (92.0, 97.0, 91.0, 96.0),
        (96.0, 100.0, 95.0, 99.0),
        (99.0, 104.0, 98.0, 103.0),
        (103.0, 110.0, 102.0, 108.0),
        (108.0, 108.0, 100.0, 102.0),
        (102.0, 103.0, 95.0, 96.0),
        (96.0, 97.0, 92.0, 93.0),
        (93.0, 94.0, 90.0, 91.0),
        (91.0, 96.0, 91.0, 95.0),
        (95.0, 100.0, 94.0, 99.0),
    ]
    return [
        _make_bar(o, h, lo, c, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c) in enumerate(data)
    ]


def _make_wick_rejection_bars() -> list[Bar]:
    """Warmup bars near 100, then 3 lower-wick rejections at ~90 and 3
    upper-wick rejections at ~110 — should yield wick_rejection levels for
    both sides.
    """
    bars: list[Bar] = []
    idx = 0
    # Warmup: small-bodied bars near 100 (no significant wicks).
    for i in range(14):
        open_ = 100.0 + (i % 3) * 0.5
        close = open_ + 0.5
        high = max(open_, close) + 0.3
        low = min(open_, close) - 0.3
        bars.append(_make_bar(open_, high, low, close,
                              ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    # Three lower-wick rejections near 90 (body=1, lower_wick=8 → ratio 8).
    for i in range(3):
        price_level = 90.0 + i * 0.2
        open_ = price_level + 8.0
        close = price_level + 9.0
        high = close + 0.5
        low = price_level
        bars.append(_make_bar(open_, high, low, close,
                              ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
        # Normal bar between rejections.
        bars.append(_make_bar(99.5, 101.0, 99.0, 100.5,
                              ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    # Three upper-wick rejections near 110.
    for i in range(3):
        price_level = 110.0 + i * 0.2
        close = price_level - 8.0
        open_ = price_level - 9.0
        low = open_ - 0.5
        high = price_level
        bars.append(_make_bar(open_, high, low, close,
                              ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
        bars.append(_make_bar(99.5, 101.0, 99.0, 100.5,
                              ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    return bars


# ---------------------------------------------------------------------------
# Catalog stub — only needs the .bars() method shape used by the route.
# ---------------------------------------------------------------------------


@dataclass
class _StubCatalog:
    bars_by_type: dict[str, list[Bar]]

    def bars(self, bar_types: list[str]) -> list[Bar]:
        out: list[Bar] = []
        for bt in bar_types:
            out.extend(self.bars_by_type.get(bt, []))
        return out


def _client_with_catalog(catalog: _StubCatalog) -> TestClient:
    app = create_app()
    app.dependency_overrides[_catalog] = lambda: catalog
    return TestClient(app)


# ---------------------------------------------------------------------------
# /api/key-levels/detectors
# ---------------------------------------------------------------------------


def test_detectors_endpoint_returns_equal_highs_lows():
    client = _client_with_catalog(_StubCatalog(bars_by_type={}))
    res = client.get("/api/key-levels/detectors")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    eql = next((d for d in data if d["id"] == "equal_highs_lows"), None)
    assert eql is not None
    assert eql["label"] == "Equal Highs/Lows"
    assert eql["color"].startswith("#")

    wick = next((d for d in data if d["id"] == "wick_rejection"), None)
    assert wick is not None
    assert wick["label"] == "Wick Rejection"
    assert wick["color"].startswith("#")


# ---------------------------------------------------------------------------
# /api/bars/{bar_type}/key-levels — happy path
# ---------------------------------------------------------------------------


def test_key_levels_returns_dtos_for_valid_bar_type():
    bars = _make_equal_highs_lows_bars()
    catalog = _StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars})
    client = _client_with_catalog(catalog)

    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "equal_highs_lows"},
    )
    assert res.status_code == 200, res.text

    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0

    for lvl in levels:
        assert lvl["source"] == "equal_highs_lows"
        assert isinstance(lvl["price"], float)
        assert isinstance(lvl["strength"], float)
        # ISO-8601 timestamps (string), end_ts may be None.
        assert isinstance(lvl["start_ts"], str)
        assert "T" in lvl["start_ts"]
        if lvl["end_ts"] is not None:
            assert isinstance(lvl["end_ts"], str)
            assert "T" in lvl["end_ts"]
        # Discriminated meta.
        meta = lvl["meta"]
        assert meta["kind"] == "equal_highs_lows"
        assert meta["side"] in ("high", "low")
        assert isinstance(meta["touch_count"], int)
        assert isinstance(meta["touch_prices"], list)


# ---------------------------------------------------------------------------
# /api/bars/{bar_type}/key-levels — wick_rejection
# ---------------------------------------------------------------------------


def test_key_levels_returns_wick_rejection_dtos():
    bars = _make_wick_rejection_bars()
    catalog = _StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars})
    client = _client_with_catalog(catalog)

    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "wick_rejection"},
    )
    assert res.status_code == 200, res.text

    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0

    for lvl in levels:
        assert lvl["source"] == "wick_rejection"
        assert isinstance(lvl["price"], float)
        assert isinstance(lvl["strength"], float)
        assert isinstance(lvl["start_ts"], str)
        assert "T" in lvl["start_ts"]
        if lvl["end_ts"] is not None:
            assert isinstance(lvl["end_ts"], str)
            assert "T" in lvl["end_ts"]
        meta = lvl["meta"]
        assert meta["kind"] == "wick_rejection"
        assert meta["side"] in ("high", "low")
        assert isinstance(meta["rejection_count"], int)
        assert meta["rejection_count"] >= 2
        assert isinstance(meta["avg_wick_ratio"], float)
        assert meta["avg_wick_ratio"] > 0.0
        assert isinstance(meta["touch_count"], int)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_key_levels_unknown_detector_returns_400():
    bars = _make_equal_highs_lows_bars()
    catalog = _StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars})
    client = _client_with_catalog(catalog)

    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "not_a_detector"},
    )
    assert res.status_code == 400
    assert "not_a_detector" in res.json()["detail"]


def test_key_levels_missing_bar_type_returns_404():
    # Empty catalog → bars(...) returns [] for any bar_type.
    catalog = _StubCatalog(bars_by_type={})
    client = _client_with_catalog(catalog)

    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "equal_highs_lows"},
    )
    assert res.status_code == 404
    assert _DEFAULT_BAR_TYPE_STR in res.json()["detail"]
