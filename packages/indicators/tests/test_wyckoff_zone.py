"""Tests for WyckoffZoneDetector — lifecycle-tracked accumulation/distribution."""

from indicators.key_levels.detectors.wyckoff_zone import WyckoffZoneDetector
from indicators.key_levels.model import WyckoffZoneMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _downtrend_then_range(
    drop_bars: int = 30,
    range_bars: int = 20,
    drop_per_bar: float = 1.0,
    start: float = 200.0,
) -> list:
    """Sharp drop followed by tight sideways range — accumulation setup."""
    bars = []
    idx = 0
    price = start
    for i in range(drop_bars):
        new_price = price - drop_per_bar
        bars.append(make_bar(price, price + 0.3, new_price - 0.3, new_price,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        price = new_price
        idx += 1
    range_center = price
    for j in range(range_bars):
        bars.append(make_bar(range_center, range_center + 0.2,
                             range_center - 0.2, range_center,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    return bars


def _uptrend_then_range(
    up_bars: int = 30,
    range_bars: int = 20,
    up_per_bar: float = 1.0,
    start: float = 100.0,
) -> list:
    bars = []
    idx = 0
    price = start
    for i in range(up_bars):
        new_price = price + up_per_bar
        bars.append(make_bar(price, new_price + 0.3, price - 0.3, new_price,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        price = new_price
        idx += 1
    range_center = price
    for j in range(range_bars):
        bars.append(make_bar(range_center, range_center + 0.2,
                             range_center - 0.2, range_center,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    return bars


def test_no_levels_in_warmup():
    det = WyckoffZoneDetector(trend_lookback=30, min_range_bars=6, atr_period=5)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_emits_accumulation_after_drop():
    det = WyckoffZoneDetector(
        trend_lookback=20,
        trend_atr_multiple=2.0,
        min_range_bars=5,
        range_atr_multiple=3.0,
        atr_period=5,
        breakout_atr=10_000.0,
        max_idle_bars=10_000,
    )
    for bar in _downtrend_then_range(drop_bars=25, range_bars=15):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1
    lvl = levels[0]
    assert lvl.source == "wyckoff_zone"
    assert isinstance(lvl.meta, WyckoffZoneMeta)
    assert lvl.meta.zone_type == "accumulation"
    assert lvl.meta.side == "low"
    assert lvl.meta.phase in ("A", "B", "C", "D", "E")
    assert isinstance(lvl.meta.touch_count, int)
    assert 0.0 <= lvl.meta.confidence <= 1.0


def test_emits_distribution_after_climb():
    det = WyckoffZoneDetector(
        trend_lookback=20,
        trend_atr_multiple=2.0,
        min_range_bars=5,
        range_atr_multiple=3.0,
        atr_period=5,
        breakout_atr=10_000.0,
        max_idle_bars=10_000,
    )
    for bar in _uptrend_then_range(up_bars=25, range_bars=15):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1
    lvl = levels[0]
    assert lvl.meta.zone_type == "distribution"
    assert lvl.meta.side == "high"


def test_breakout_finalizes_zone():
    det = WyckoffZoneDetector(
        trend_lookback=20,
        trend_atr_multiple=2.0,
        min_range_bars=5,
        range_atr_multiple=3.0,
        atr_period=5,
        breakout_atr=0.5,
        breakout_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    bars = _downtrend_then_range(drop_bars=25, range_bars=10)
    # Append a strong upside breakout — Phase E for accumulation.
    last_idx = len(bars)
    for i in range(6):
        ts = _BASE_TS + (last_idx + i) * _1H_NS
        bars.append(make_bar(220.0 + i, 225.0 + i, 219.0 + i, 224.0 + i,
                             ts_ns=ts))
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is not None for lv in levels), \
        "expected zone to finalize on breakout"
    finalized = next(lv for lv in levels if lv.end_ts is not None)
    assert finalized.meta.phase == "E"


def test_active_zones_have_no_end_ts():
    det = WyckoffZoneDetector(
        trend_lookback=20,
        trend_atr_multiple=2.0,
        min_range_bars=5,
        range_atr_multiple=3.0,
        atr_period=5,
        breakout_atr=10_000.0,
        max_idle_bars=10_000,
    )
    for bar in _downtrend_then_range(drop_bars=25, range_bars=15):
        det.update(bar)
    assert any(lv.end_ts is None for lv in det.levels())


def test_deterministic():
    bars = _downtrend_then_range(drop_bars=25, range_bars=15)
    cfg = dict(
        trend_lookback=20, trend_atr_multiple=2.0, min_range_bars=5,
        range_atr_multiple=3.0, atr_period=5, breakout_atr=1.0,
    )
    a = WyckoffZoneDetector(**cfg)
    b = WyckoffZoneDetector(**cfg)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = WyckoffZoneDetector(
        trend_lookback=20, trend_atr_multiple=2.0, min_range_bars=5,
        range_atr_multiple=3.0, atr_period=5,
    )
    for bar in _downtrend_then_range(drop_bars=25, range_bars=15):
        det.update(bar)
    det.reset()
    assert det.levels() == []
