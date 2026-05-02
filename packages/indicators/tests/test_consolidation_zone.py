"""Tests for ConsolidationZoneDetector — lifecycle-tracked levels."""

from indicators.key_levels.detectors.consolidation_zone import (
    ConsolidationZoneDetector,
)
from indicators.key_levels.model import ConsolidationZoneMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _flat_bars(count: int = 80) -> list:
    """Tightly bounded bars that should pass slope + volatility tests."""
    bars: list = []
    for i in range(count):
        # Tiny oscillation around 100 so ATR is small but non-zero.
        center = 100.0 + (0.05 if i % 2 == 0 else -0.05)
        bars.append(make_bar(
            center, center + 0.1, center - 0.1, center + 0.02,
            ts_ns=_BASE_TS + i * _1H_NS,
        ))
    return bars


def test_no_levels_before_warmup():
    det = ConsolidationZoneDetector(min_range_bars=20, atr_period=14)
    det.update(make_bar(100.0, 101.0, 99.0, 100.0))
    assert det.levels() == []


def test_consolidation_zone_emitted():
    """Need long_atr to be ready (3*atr_period) plus the prior period
    of activity to compress current ATR. Use ramp-then-flat sequence."""
    bars: list = []
    # Active period that loads long_atr with larger ranges.
    for i in range(60):
        ts = _BASE_TS + i * _1H_NS
        # Wider bars early.
        center = 100.0 + (i % 10) * 0.5
        bars.append(make_bar(
            center, center + 1.5, center - 1.5, center + 0.1, ts_ns=ts,
        ))
    # Then a tightly bounded flat zone.
    base_idx = len(bars)
    for j in range(40):
        ts = _BASE_TS + (base_idx + j) * _1H_NS
        center = 100.0 + (0.05 if j % 2 == 0 else -0.05)
        bars.append(make_bar(
            center, center + 0.1, center - 0.1, center + 0.02, ts_ns=ts,
        ))

    det = ConsolidationZoneDetector(
        min_range_bars=20,
        max_slope=0.001,
        volatility_threshold=0.5,
        atr_period=14,
    )
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert levels, "expected a consolidation zone"
    lv = levels[0]
    assert lv.source == "consolidation_zone"
    assert isinstance(lv.meta, ConsolidationZoneMeta)
    assert lv.zone_upper is not None and lv.zone_lower is not None
    assert lv.meta.duration_bars >= 20
    assert lv.meta.range_atr_multiple >= 0.0


def test_active_zone_has_no_end_ts():
    bars = []
    for i in range(60):
        ts = _BASE_TS + i * _1H_NS
        center = 100.0 + (i % 10) * 0.5
        bars.append(make_bar(
            center, center + 1.5, center - 1.5, center + 0.1, ts_ns=ts,
        ))
    base_idx = len(bars)
    for j in range(40):
        ts = _BASE_TS + (base_idx + j) * _1H_NS
        center = 100.0 + (0.05 if j % 2 == 0 else -0.05)
        bars.append(make_bar(
            center, center + 0.1, center - 0.1, center + 0.02, ts_ns=ts,
        ))

    det = ConsolidationZoneDetector(min_range_bars=20, atr_period=14)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_reset_clears_state():
    det = ConsolidationZoneDetector(min_range_bars=20, atr_period=14)
    for bar in _flat_bars(60):
        det.update(bar)
    det.reset()
    assert det.levels() == []


def test_meta_side_set():
    bars: list = []
    for i in range(60):
        ts = _BASE_TS + i * _1H_NS
        center = 100.0 + (i % 10) * 0.5
        bars.append(make_bar(
            center, center + 1.5, center - 1.5, center + 0.1, ts_ns=ts,
        ))
    base_idx = len(bars)
    for j in range(40):
        ts = _BASE_TS + (base_idx + j) * _1H_NS
        center = 100.0 + (0.05 if j % 2 == 0 else -0.05)
        bars.append(make_bar(
            center, center + 0.1, center - 0.1, center + 0.02, ts_ns=ts,
        ))
    det = ConsolidationZoneDetector(min_range_bars=20, atr_period=14)
    for bar in bars:
        det.update(bar)
    for lv in det.levels():
        assert lv.meta.side in ("high", "low")
        assert isinstance(lv.meta.touch_count, int)
