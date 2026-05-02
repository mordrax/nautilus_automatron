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

    expected_ids = {
        "equal_highs_lows",
        "wick_rejection",
        "atr_volatility",
        "fib_retracement",
        "fib_extension",
        "pivot_standard",
        "pivot_fibonacci",
        "pivot_camarilla",
        "pivot_woodie",
        "pivot_demark",
        "psychological",
        "volume_profile",
        "volume_distribution",
        "anchored_vwap",
        "cvd",
        "session_level",
        "periodic_level",
        "opening_range",
        "market_profile_tpo",
        "swing_cluster",
        "order_block",
        "fair_value_gap",
        "price_gap",
        "darvas_box",
        "consolidation_zone",
    }
    returned_ids = {d["id"] for d in data}
    assert expected_ids.issubset(returned_ids)

    for d in data:
        assert d["color"].startswith("#")
        assert d["label"]

    eql = next((d for d in data if d["id"] == "equal_highs_lows"), None)
    assert eql is not None
    assert eql["label"] == "Equal Highs/Lows"

    wick = next((d for d in data if d["id"] == "wick_rejection"), None)
    assert wick is not None
    assert wick["label"] == "Wick Rejection"


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


# ---------------------------------------------------------------------------
# Smoke tests for the migrated detectors (#120) — verify the route returns
# valid DTOs with the matching `meta.kind` discriminator.
# ---------------------------------------------------------------------------


def _make_stable_bars(count: int = 60, base_price: float = 1075.0) -> list[Bar]:
    """Stable bars around `base_price` — enough for any detector to warm up."""
    bars: list[Bar] = []
    for i in range(count):
        # Small oscillation so swings can form for fib/atr_volatility.
        center = base_price + (i % 5 - 2) * 1.5
        o = center
        c = center + 0.5
        h = max(o, c) + 1.0
        lo = min(o, c) - 1.0
        bars.append(_make_bar(o, h, lo, c, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def test_key_levels_atr_volatility_route():
    bars = _make_stable_bars(count=30)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "atr_volatility"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "atr_volatility"
        assert lvl["meta"]["kind"] == "atr_volatility"
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_fib_retracement_route():
    # Build a clear swing pattern for fib retracement.
    bars = _make_stable_bars(count=30)
    # Append a clear swing-low then swing-high.
    idx = len(bars)
    for o, h, lo, c in [
        (1090, 1090, 1075, 1080),
        (1080, 1080, 1060, 1065),
        (1065, 1065, 1050, 1055),  # forming low
        (1055, 1070, 1050, 1068),  # bounce
        (1068, 1085, 1066, 1083),
        (1083, 1100, 1080, 1098),
        (1098, 1115, 1095, 1112),  # forming high
        (1112, 1115, 1100, 1102),
        (1102, 1108, 1095, 1098),
        (1098, 1100, 1085, 1090),
        (1090, 1095, 1080, 1085),
    ]:
        bars.append(_make_bar(o, h, lo, c, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "fib_retracement"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    # Even if no fan emits, the response must be a valid list.
    for lvl in levels:
        assert lvl["source"] == "fib_retracement"
        assert lvl["meta"]["kind"] == "fibonacci"
        assert lvl["meta"]["direction"] == "retracement"


def test_key_levels_pivot_standard_route():
    # period_bars=24 default → need at least 24 bars for one pivot set.
    bars = _make_stable_bars(count=30)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "pivot_standard"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "pivot_standard"
        assert lvl["meta"]["kind"] == "pivot_point"
        assert lvl["meta"]["variant"] == "standard"


def test_key_levels_psychological_route():
    bars = _make_stable_bars(count=30, base_price=1075.0)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "psychological"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "psychological"
        assert lvl["meta"]["kind"] == "psychological"
        assert lvl["meta"]["tier"] in ("major", "minor", "micro")


# ---------------------------------------------------------------------------
# Smoke tests for the migrated detectors (#121).
# ---------------------------------------------------------------------------


def _make_swing_bars(swing_count: int = 4, period: int = 5) -> list[Bar]:
    """OHLCV bars with `swing_count` confirmed alternating fractal swings."""
    bars: list[Bar] = []
    centers = [100.0, 110.0, 95.0, 115.0, 90.0, 120.0, 88.0, 122.0]
    centers = centers[:swing_count]

    idx = 0
    base = 100.0
    for target in centers:
        going_up = target > base
        for j in range(period):
            frac = (j + 1) / (period + 1)
            price = base + (target - base) * frac
            o = price - 0.3
            cl = price + 0.3
            h = max(o, cl) + 0.5
            lo = min(o, cl) - 0.5
            bars.append(_make_bar(o, h, lo, cl, ts_ns=_BASE_TS + idx * _1H_NS))
            idx += 1
        if going_up:
            bars.append(_make_bar(target - 0.3, target + 1.0, target - 0.5, target,
                                  ts_ns=_BASE_TS + idx * _1H_NS))
        else:
            bars.append(_make_bar(target + 0.3, target + 0.5, target - 1.0, target,
                                  ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
        base = target

    last_dir = -1 if centers[-1] > centers[-2] else 1
    for j in range(period):
        price = base + last_dir * (j + 1) * 0.5
        o = price - 0.3
        cl = price + 0.3
        h = max(o, cl) + 0.5
        lo = min(o, cl) - 0.5
        bars.append(_make_bar(o, h, lo, cl, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    return bars


def test_key_levels_volume_profile_route():
    bars = _make_stable_bars(count=60)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "volume_profile"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "volume_profile"
        assert lvl["meta"]["kind"] == "volume_profile"
        assert lvl["meta"]["node_type"] in (
            "poc", "hvn", "lvn", "va_high", "va_low",
        )
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_volume_distribution_route():
    bars = _make_swing_bars(swing_count=4, period=5)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "volume_distribution"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    for lvl in levels:
        assert lvl["source"] == "volume_distribution"
        assert lvl["meta"]["kind"] == "volume_distribution"
        assert lvl["meta"]["context"] in (
            "consolidation", "peak", "trough", "range",
        )
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_anchored_vwap_route():
    bars = _make_swing_bars(swing_count=3, period=5)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "anchored_vwap"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    for lvl in levels:
        assert lvl["source"] == "anchored_vwap"
        assert lvl["meta"]["kind"] == "anchored_vwap"
        assert lvl["meta"]["anchor_type"] in (
            "swing_high", "swing_low", "gap", "volume_spike",
        )
        assert lvl["meta"]["side"] in ("high", "low")


def _make_cvd_bars() -> list[Bar]:
    """Bars whose buy/sell volume estimate produces clear CVD swings."""
    bars: list[Bar] = []
    idx = 0

    def push(o: float, h: float, lo: float, cl: float) -> None:
        nonlocal idx
        bars.append(_make_bar(o, h, lo, cl, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    base = 100.0
    for i in range(8):
        o = base + i * 0.2
        push(o, o + 1.0, o - 0.1, o + 1.0)

    last_close = bars[-1].close.as_double()
    for i in range(8):
        o = last_close - i * 0.2
        push(o, o + 0.1, o - 1.0, o - 1.0)

    last_close = bars[-1].close.as_double()
    for i in range(8):
        o = last_close + i * 0.2
        push(o, o + 1.0, o - 0.1, o + 1.0)

    last_close = bars[-1].close.as_double()
    for i in range(8):
        o = last_close - i * 0.2
        push(o, o + 0.1, o - 1.0, o - 1.0)

    return bars


def test_key_levels_cvd_route():
    bars = _make_cvd_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "cvd"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "cvd"
        assert lvl["meta"]["kind"] == "cvd"
        assert lvl["meta"]["divergence"] in ("bullish", "bearish", "none")
        assert lvl["meta"]["side"] in ("high", "low")


# ---------------------------------------------------------------------------
# Smoke tests for the migrated detectors (#122).
# ---------------------------------------------------------------------------


def _make_session_bars(days: int = 2) -> list[Bar]:
    """24 hourly bars per day for `days` days — exercises Asian/London/NY
    session windows so SessionLevelDetector emits levels.
    """
    bars: list[Bar] = []
    idx = 0
    for d in range(days):
        for h in range(24):
            ts = _BASE_TS + d * 24 * _1H_NS + h * _1H_NS
            base = 100.0 + d
            spike = 0.0
            if 0 <= h < 8:
                spike = 1.0 if h == 4 else 0.0
            elif 7 <= h < 16:
                spike = 2.0 if h == 11 else 0.0
            elif 12 <= h < 21:
                spike = 3.0 if h == 17 else 0.0
            o = base + spike
            c = base + spike + 0.2
            hi = max(o, c) + 0.3
            lo = min(o, c) - 0.3
            bars.append(_make_bar(o, hi, lo, c, ts_ns=ts))
            idx += 1
    return bars


def test_key_levels_session_level_route():
    bars = _make_session_bars(days=2)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "session_level"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "session_level"
        assert lvl["meta"]["kind"] == "session_level"
        assert lvl["meta"]["session"] in ("asian", "london", "new_york", "custom")
        assert lvl["meta"]["role"] in ("high", "low")
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_periodic_level_route():
    # Span at least 3 days so daily period rolls over and emits levels.
    bars = _make_session_bars(days=3)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "periodic_level"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "periodic_level"
        assert lvl["meta"]["kind"] == "periodic_level"
        assert lvl["meta"]["period"] in ("daily", "weekly", "monthly")
        assert lvl["meta"]["role"] in ("high", "low")
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_opening_range_route():
    # Need bars spanning the open hour (9 UTC default) for >= range_minutes,
    # plus past the lock — 2 days of hourly bars covers it.
    bars = _make_session_bars(days=2)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "opening_range"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    # Even if range hasn't locked, response shape must be valid.
    for lvl in levels:
        assert lvl["source"] == "opening_range"
        assert lvl["meta"]["kind"] == "opening_range"
        assert lvl["meta"]["role"] in ("high", "low")
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_market_profile_route():
    # 2 days = at least one prior session's TPO profile to build levels from.
    bars = _make_session_bars(days=2)
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "market_profile_tpo"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    for lvl in levels:
        assert lvl["source"] == "market_profile_tpo"
        assert lvl["meta"]["kind"] == "market_profile_tpo"
        assert lvl["meta"]["role"] in ("poc", "vah", "val")
        assert lvl["meta"]["side"] in ("high", "low")


def test_key_levels_swing_cluster_route():
    bars = _make_equal_highs_lows_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "swing_cluster"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    for lvl in levels:
        assert lvl["source"] == "swing_cluster"
        assert lvl["meta"]["kind"] == "swing_cluster"
        assert lvl["meta"]["side"] in ("high", "low")
        assert isinstance(lvl["meta"]["pivot_indices"], list)


# ---------------------------------------------------------------------------
# Smoke tests for the migrated detectors (#123) — Phase 5 (price action).
# ---------------------------------------------------------------------------


def _make_displacement_bars() -> list[Bar]:
    """Stable warmup, then a bearish candle followed by a strong bullish
    displacement — should yield a bullish order block AND likely a bullish FVG.
    """
    bars: list[Bar] = []
    for i in range(20):
        ts = _BASE_TS + i * _1H_NS
        bars.append(_make_bar(100.0, 100.5, 99.5, 100.0, ts_ns=ts))
    idx = len(bars)
    bars.append(_make_bar(102.0, 102.5, 99.5, 100.0,
                          ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(_make_bar(100.0, 110.5, 100.0, 110.0,
                          ts_ns=_BASE_TS + idx * _1H_NS))
    return bars


def test_key_levels_order_block_route():
    bars = _make_displacement_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "order_block"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "order_block"
        assert lvl["meta"]["kind"] == "order_block"
        assert lvl["meta"]["block_side"] in ("bullish", "bearish")
        assert lvl["meta"]["side"] in ("high", "low")
        assert isinstance(lvl["meta"]["displacement_atr_multiple"], float)
        assert isinstance(lvl["meta"]["mitigation_pct"], float)


def _make_fvg_bars() -> list[Bar]:
    bars: list[Bar] = []
    for i in range(20):
        ts = _BASE_TS + i * _1H_NS
        bars.append(_make_bar(100.0, 100.5, 99.5, 100.0, ts_ns=ts))
    idx = len(bars)
    bars.append(_make_bar(100.0, 100.5, 99.5, 100.0,
                          ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(_make_bar(101.0, 105.0, 100.5, 104.0,
                          ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(_make_bar(106.0, 108.0, 105.0, 107.0,
                          ts_ns=_BASE_TS + idx * _1H_NS))
    return bars


def test_key_levels_fair_value_gap_route():
    bars = _make_fvg_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "fair_value_gap"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "fair_value_gap"
        assert lvl["meta"]["kind"] == "fair_value_gap"
        assert lvl["meta"]["gap_side"] in ("bullish", "bearish")
        assert lvl["meta"]["side"] in ("high", "low")
        assert isinstance(lvl["meta"]["gap_size"], float)
        assert isinstance(lvl["meta"]["fill_percentage"], float)


def _make_price_gap_bars() -> list[Bar]:
    bars: list[Bar] = []
    for i in range(25):
        ts = _BASE_TS + i * _1H_NS
        bars.append(_make_bar(100.0, 100.5, 99.5, 100.0, ts_ns=ts))
    idx = len(bars)
    bars.append(_make_bar(106.0, 108.0, 105.0, 107.0,
                          ts_ns=_BASE_TS + idx * _1H_NS))
    return bars


def test_key_levels_price_gap_route():
    bars = _make_price_gap_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "price_gap"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "price_gap"
        assert lvl["meta"]["kind"] == "price_gap"
        assert lvl["meta"]["gap_type"] in (
            "breakaway", "runaway", "exhaustion", "common",
        )
        assert lvl["meta"]["level_type"] in ("upper", "lower")
        assert lvl["meta"]["side"] in ("high", "low")


def _make_darvas_bars() -> list[Bar]:
    bars: list[Bar] = []
    for i in range(19):
        price = 100.0 + i * 0.5
        ts = _BASE_TS + i * _1H_NS
        bars.append(_make_bar(price - 0.1, price + 0.5, price - 0.5,
                              price + 0.3, ts_ns=ts))
    bars.append(_make_bar(109.5, 112.0, 109.0, 111.0,
                          ts_ns=_BASE_TS + 19 * _1H_NS))
    for j in range(5):
        ts = _BASE_TS + (20 + j) * _1H_NS
        bars.append(_make_bar(109.0, 110.5, 108.0, 109.5, ts_ns=ts))
    return bars


def test_key_levels_darvas_box_route():
    bars = _make_darvas_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "darvas_box"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "darvas_box"
        assert lvl["meta"]["kind"] == "darvas_box"
        assert isinstance(lvl["meta"]["confirmed"], bool)
        assert lvl["meta"]["side"] in ("high", "low")


def _make_consolidation_bars() -> list[Bar]:
    bars: list[Bar] = []
    # Active period (loads long_atr).
    for i in range(60):
        ts = _BASE_TS + i * _1H_NS
        center = 100.0 + (i % 10) * 0.5
        bars.append(_make_bar(center, center + 1.5, center - 1.5,
                              center + 0.1, ts_ns=ts))
    # Tightly bounded flat zone.
    base_idx = len(bars)
    for j in range(40):
        ts = _BASE_TS + (base_idx + j) * _1H_NS
        center = 100.0 + (0.05 if j % 2 == 0 else -0.05)
        bars.append(_make_bar(center, center + 0.1, center - 0.1,
                              center + 0.02, ts_ns=ts))
    return bars


def test_key_levels_consolidation_zone_route():
    bars = _make_consolidation_bars()
    client = _client_with_catalog(_StubCatalog(bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}))
    res = client.get(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/key-levels",
        params={"detectors": "consolidation_zone"},
    )
    assert res.status_code == 200, res.text
    levels = res.json()
    assert isinstance(levels, list)
    assert len(levels) > 0
    for lvl in levels:
        assert lvl["source"] == "consolidation_zone"
        assert lvl["meta"]["kind"] == "consolidation_zone"
        assert isinstance(lvl["meta"]["duration_bars"], int)
        assert isinstance(lvl["meta"]["range_atr_multiple"], float)
        assert lvl["meta"]["side"] in ("high", "low")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


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
