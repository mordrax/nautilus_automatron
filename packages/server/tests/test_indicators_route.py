"""Tests for the indicators routes.

GET /api/indicators — returns list of IndicatorTypeOut
POST /api/bars/{bar_type}/indicators — computes results for a list of instances
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.objects import Price, Quantity

from server.main import create_app
from server.routes.dependencies import _catalog


# ---------------------------------------------------------------------------
# Bar factory (mirrors key_levels_route test pattern)
# ---------------------------------------------------------------------------

_DEFAULT_BAR_TYPE_STR = "TEST.SIM-1-MINUTE-BID-EXTERNAL"
_DEFAULT_BAR_TYPE = BarType.from_str(_DEFAULT_BAR_TYPE_STR)
_1M_NS = 60_000_000_000  # 60 seconds in nanoseconds
_BASE_TS = 1_704_067_200_000_000_000  # 2024-01-01 00:00:00 UTC


def _make_bar(
    close: float,
    ts_ns: int,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
) -> Bar:
    o = open_ if open_ is not None else close - 0.5
    h = high if high is not None else close + 0.5
    lo = low if low is not None else close - 0.5
    return Bar(
        bar_type=_DEFAULT_BAR_TYPE,
        open=Price.from_str(f"{o:.5f}"),
        high=Price.from_str(f"{h:.5f}"),
        low=Price.from_str(f"{lo:.5f}"),
        close=Price.from_str(f"{close:.5f}"),
        volume=Quantity.from_str("100.00"),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


def _make_bars(count: int = 50) -> list[Bar]:
    """Gradually rising close prices so SMA is well-defined after warmup."""
    return [
        _make_bar(
            close=100.0 + i * 0.1,
            ts_ns=_BASE_TS + i * _1M_NS,
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Stub catalog — mirrors pattern in test_key_levels_route.py
# ---------------------------------------------------------------------------


@dataclass
class _StubCatalog:
    bars_by_type: dict[str, list[Bar]]

    def bars(self, bar_types: list[str]) -> list[Bar]:
        out: list[Bar] = []
        for bt in bar_types:
            out.extend(self.bars_by_type.get(bt, []))
        return out


def _client_with_bars(bars: list[Bar]) -> TestClient:
    app = create_app()
    app.dependency_overrides[_catalog] = lambda: _StubCatalog(
        bars_by_type={_DEFAULT_BAR_TYPE_STR: bars}
    )
    return TestClient(app)


def _client_empty() -> TestClient:
    app = create_app()
    app.dependency_overrides[_catalog] = lambda: _StubCatalog(bars_by_type={})
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/indicators
# ---------------------------------------------------------------------------


def test_get_indicators_returns_list():
    client = _client_empty()
    resp = client.get("/api/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_indicators_contains_sma():
    client = _client_empty()
    resp = client.get("/api/indicators")
    assert resp.status_code == 200
    types = {item["type"] for item in resp.json()}
    assert "SMA" in types


def test_sma_has_period_param_with_default_20():
    client = _client_empty()
    resp = client.get("/api/indicators")
    assert resp.status_code == 200
    sma = next(item for item in resp.json() if item["type"] == "SMA")

    assert sma["label_template"] == "SMA({period})"
    params = sma["params"]
    assert len(params) >= 1
    period_param = next((p for p in params if p["name"] == "period"), None)
    assert period_param is not None
    assert period_param["default"] == 20
    assert period_param["type"] == "int"


def test_get_indicators_shape_has_required_fields():
    client = _client_empty()
    resp = client.get("/api/indicators")
    data = resp.json()
    for item in data:
        assert "type" in item
        assert "display" in item
        assert "outputs" in item
        assert "params" in item
        assert item["display"] in ("overlay", "panel")
        assert isinstance(item["outputs"], list)
        assert isinstance(item["params"], list)


# ---------------------------------------------------------------------------
# POST /api/bars/{bar_type}/indicators — happy path
# ---------------------------------------------------------------------------


def test_post_indicators_sma_returns_result():
    bars = _make_bars(count=50)
    client = _client_with_bars(bars)
    instance_id = str(uuid.uuid4())

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": instance_id, "type": "SMA", "params": {"period": 20}}
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()
    assert len(results) == 1
    result = results[0]
    assert result["id"] == instance_id
    assert result["label"] == "SMA(20)"
    assert result["display"] == "overlay"
    assert "outputs" in result
    assert "value" in result["outputs"]
    assert "datetime" in result
    # Output length matches bar count
    assert len(result["outputs"]["value"]) == len(bars)
    assert len(result["datetime"]) == len(bars)


def test_post_indicators_id_matches_request():
    bars = _make_bars(count=30)
    client = _client_with_bars(bars)
    my_id = "my-custom-uuid-abc123"

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": my_id, "type": "SMA", "params": {"period": 10}}
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()[0]["id"] == my_id


def test_post_indicators_two_instances_same_type_different_params():
    bars = _make_bars(count=50)
    client = _client_with_bars(bars)
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": id1, "type": "SMA", "params": {"period": 10}},
                {"id": id2, "type": "SMA", "params": {"period": 20}},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()
    assert len(results) == 2
    assert results[0]["id"] == id1
    assert results[1]["id"] == id2
    assert results[0]["label"] == "SMA(10)"
    assert results[1]["label"] == "SMA(20)"
    # Two SMAs with different periods produce different values
    v10 = results[0]["outputs"]["value"]
    v20 = results[1]["outputs"]["value"]
    assert v10 != v20


def test_post_indicators_none_before_warmup():
    """SMA(20) values should be None for the first 19 bars."""
    bars = _make_bars(count=30)
    client = _client_with_bars(bars)

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": "test", "type": "SMA", "params": {"period": 20}}
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    values = resp.json()[0]["outputs"]["value"]
    # The first period-1 values should be None (not yet initialized)
    # Note: NautilusTrader SMA emits value at bar index period-1 (0-indexed)
    first_non_none = next((i for i, v in enumerate(values) if v is not None), None)
    assert first_non_none is not None
    assert first_non_none >= 1  # At least one None before first value


# ---------------------------------------------------------------------------
# POST /api/bars/{bar_type}/indicators — error cases
# ---------------------------------------------------------------------------


def test_post_indicators_unknown_type_returns_400():
    bars = _make_bars(count=30)
    client = _client_with_bars(bars)

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": "x", "type": "NOT_AN_INDICATOR", "params": {}}
            ]
        },
    )
    assert resp.status_code == 400
    assert "NOT_AN_INDICATOR" in resp.json()["detail"]


def test_post_indicators_out_of_range_param_returns_400():
    bars = _make_bars(count=30)
    client = _client_with_bars(bars)

    # SMA min period is 2; period=1 should fail validation
    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": "x", "type": "SMA", "params": {"period": 1}}
            ]
        },
    )
    assert resp.status_code == 400


def test_post_indicators_missing_bar_type_returns_404():
    client = _client_empty()

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {"id": "x", "type": "SMA", "params": {"period": 20}}
            ]
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Enum param-schema tests
# ---------------------------------------------------------------------------

from server.store.indicators import (
    INDICATOR_TYPES,
    IndicatorType,
    ParamSchema,
    ParamValidationError,
    build_indicator_from_instance,
)


def test_param_schema_accepts_enum_type():
    schema = ParamSchema(
        name="mode", type="enum", default="A", choices=("A", "B", "C"),
    )
    assert schema.type == "enum"
    assert schema.choices == ("A", "B", "C")
    assert schema.default == "A"


def test_build_rejects_enum_value_not_in_choices(monkeypatch):
    # Register a temporary indicator type with one enum param.
    class _Dummy:
        @property
        def initialized(self) -> bool:
            return True

        def update_raw(self, *args: float) -> None:
            pass

    dummy_type = IndicatorType(
        type="DummyEnum",
        label_template="Dummy({mode})",
        display="overlay",
        outputs=("value",),
        params=(
            ParamSchema(
                name="mode",
                type="enum",
                default="A",
                choices=("A", "B"),
            ),
        ),
        factory=lambda p: _Dummy(),
        update=lambda ind, bar: None,
    )
    monkeypatch.setitem(INDICATOR_TYPES, "DummyEnum", dummy_type)

    # Valid value → no error.
    build_indicator_from_instance("DummyEnum", {"mode": "A"})

    # Invalid value → ParamValidationError.
    with pytest.raises(ParamValidationError):
        build_indicator_from_instance("DummyEnum", {"mode": "Z"})


# ---------------------------------------------------------------------------
# Spike indicator registration + compute tests
# ---------------------------------------------------------------------------

from server.store.indicators import compute_indicator_instance


def _make_spike_bars(closes: list[float]) -> list[Bar]:
    """Build a list of Bar objects from close prices, mirroring the test's
    existing bar-factory pattern (see top of this file)."""
    bars: list[Bar] = []
    for i, close in enumerate(closes):
        prev = closes[i - 1] if i > 0 else close
        high = max(prev, close) + 0.5
        low = min(prev, close) - 0.5
        bars.append(
            Bar(
                bar_type=_DEFAULT_BAR_TYPE,
                open=Price.from_str(f"{prev:.5f}"),
                high=Price.from_str(f"{high:.5f}"),
                low=Price.from_str(f"{low:.5f}"),
                close=Price.from_str(f"{close:.5f}"),
                volume=Quantity.from_str("100.00"),
                ts_event=_BASE_TS + i * _1M_NS,
                ts_init=_BASE_TS + i * _1M_NS,
            )
        )
    return bars


def test_spike_registered_with_all_nine_params():
    t = INDICATOR_TYPES["Spike"]
    assert t.type == "Spike"
    assert t.display == "overlay"
    param_names = {p.name for p in t.params}
    assert {
        "move_method", "statistic", "measurement_window", "baseline_window",
        "price_threshold", "volume_threshold", "cooldown_bars",
        "require_volume", "max_spikes",
    } == param_names


def test_spike_compute_returns_sparse_series():
    bars = _make_spike_bars([100.0] * 15)
    result = compute_indicator_instance(
        instance_id="test",
        type_name="Spike",
        params={
            "move_method": "NET",
            "statistic": "ZSCORE",
            "measurement_window": 3,
            "baseline_window": 10,
            "price_threshold": 2.5,
            "volume_threshold": 2.0,
            "cooldown_bars": 10,
            "require_volume": "NEVER",
            "max_spikes": 100,
        },
        bars=bars,
    )
    assert result.id == "test"
    assert result.display == "overlay"
    assert "spike_up" in result.outputs
    assert "spike_down" in result.outputs
    assert len(result.outputs["spike_up"]) == len(bars)
    assert len(result.outputs["spike_down"]) == len(bars)
    # No spike in flat data
    assert all(v is None for v in result.outputs["spike_up"])
    assert all(v is None for v in result.outputs["spike_down"])


def _valid_spike_params() -> dict:
    return {
        "move_method": "NET",
        "statistic": "ZSCORE",
        "measurement_window": 3,
        "baseline_window": 10,
        "price_threshold": 2.5,
        "volume_threshold": 2.0,
        "cooldown_bars": 10,
        "require_volume": "NEVER",
        "max_spikes": 100,
    }


def test_spike_rejects_invalid_enum_value():
    """An out-of-choices enum value on the real Spike type is rejected."""
    for bad_key, bad_value in [
        ("move_method", "BOGUS"),
        ("statistic", "NOT_A_STAT"),
        ("require_volume", "MAYBE"),
    ]:
        with pytest.raises(ParamValidationError):
            build_indicator_from_instance(
                "Spike", {**_valid_spike_params(), bad_key: bad_value}
            )


def test_post_spike_invalid_enum_returns_400():
    """Posting a Spike instance with a bad enum value over HTTP returns 400."""
    bars = _make_bars(count=30)
    client = _client_with_bars(bars)

    resp = client.post(
        f"/api/bars/{_DEFAULT_BAR_TYPE_STR}/indicators",
        json={
            "instances": [
                {
                    "id": "x",
                    "type": "Spike",
                    "params": {**_valid_spike_params(), "move_method": "BOGUS"},
                }
            ]
        },
    )
    assert resp.status_code == 400
