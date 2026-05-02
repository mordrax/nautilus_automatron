"""Tests for MaConfluenceDetector — lifecycle-tracked moving-average confluence."""

from indicators.key_levels.detectors.ma_confluence import MaConfluenceDetector
from indicators.key_levels.model import MaConfluenceMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _flat_bars(count: int = 80, price: float = 100.0) -> list:
    """Bars all sitting at one price — every EMA collapses onto it, so any
    config will hit confluence quickly."""
    bars = []
    for i in range(count):
        bars.append(make_bar(price, price + 0.05, price - 0.05, price,
                             ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def _trending_then_flat(
    trend_bars: int = 60,
    flat_bars: int = 60,
    start: float = 100.0,
    drift: float = 0.5,
) -> list:
    """Drift up, then flatten — flat phase pulls EMAs together."""
    bars = []
    idx = 0
    price = start
    for i in range(trend_bars):
        price += drift
        bars.append(make_bar(price - 0.1, price + 0.3, price - 0.3, price,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    final = price
    for j in range(flat_bars):
        bars.append(make_bar(final, final + 0.05, final - 0.05, final,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    return bars


def test_no_levels_in_warmup():
    det = MaConfluenceDetector(
        ma_periods=(5, 10), min_converging=2, atr_period=5,
    )
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_emits_level_on_confluence():
    det = MaConfluenceDetector(
        ma_periods=(5, 10, 15),
        min_converging=2,
        spread_threshold=2.0,
        atr_period=5,
    )
    for bar in _flat_bars(count=60):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1
    lvl = levels[0]
    assert lvl.source == "ma_confluence"
    assert isinstance(lvl.meta, MaConfluenceMeta)
    assert lvl.meta.ma_count >= 2
    assert lvl.meta.side in ("high", "low")
    assert isinstance(lvl.meta.touch_count, int)
    assert isinstance(lvl.meta.ma_periods, tuple)


def test_break_finalizes_level():
    """A spike that breaks the cluster centroid by `break_atr_multiple * ATR`
    for `break_consecutive_bars` bars, while the cluster itself doesn't have
    time to follow, finalizes the level via the break path. Using a high
    `confluence_break_atr` ensures the level isn't replaced via drift first.
    """
    det = MaConfluenceDetector(
        ma_periods=(50, 100),  # slow EMAs — won't follow a few-bar spike
        min_converging=2,
        spread_threshold=10.0,
        atr_period=5,
        break_atr_multiple=0.5,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
        confluence_break_atr=10_000.0,
    )
    bars = _flat_bars(count=120, price=100.0)
    last_idx = len(bars)
    # Sustained breakout candles far above the cluster.
    for i in range(6):
        ts = _BASE_TS + (last_idx + i) * _1H_NS
        bars.append(make_bar(120.0 + i, 125.0 + i, 119.0 + i, 124.0 + i,
                             ts_ns=ts))
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is not None for lv in levels), \
        "expected at least one level to finalize"


def test_replacement_on_drift():
    """Long flat then big drift — old level finalizes, new one emits."""
    det = MaConfluenceDetector(
        ma_periods=(5, 10),
        min_converging=2,
        spread_threshold=5.0,
        atr_period=5,
        confluence_break_atr=0.5,
        break_atr_multiple=10_000.0,
        max_idle_bars=10_000,
    )
    bars = _flat_bars(count=60, price=100.0)
    # Then drift down to a new flat range so EMAs cluster at a new level.
    last_idx = len(bars)
    for i in range(60):
        new_price = 80.0
        ts = _BASE_TS + (last_idx + i) * _1H_NS
        bars.append(make_bar(new_price, new_price + 0.05, new_price - 0.05,
                             new_price, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    # At least 2 levels emitted total (original + replacement).
    assert len(levels) >= 2


def test_active_levels_have_no_end_ts():
    det = MaConfluenceDetector(
        ma_periods=(5, 10),
        min_converging=2,
        spread_threshold=5.0,
        atr_period=5,
        break_atr_multiple=10_000.0,
        max_idle_bars=10_000,
    )
    for bar in _flat_bars(count=60):
        det.update(bar)
    assert any(lv.end_ts is None for lv in det.levels())


def test_deterministic():
    bars = _flat_bars(count=60)
    a = MaConfluenceDetector(ma_periods=(5, 10), min_converging=2,
                             spread_threshold=2.0, atr_period=5)
    b = MaConfluenceDetector(ma_periods=(5, 10), min_converging=2,
                             spread_threshold=2.0, atr_period=5)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = MaConfluenceDetector(ma_periods=(5, 10), min_converging=2,
                               spread_threshold=2.0, atr_period=5)
    for bar in _flat_bars(count=40):
        det.update(bar)
    det.reset()
    assert det.levels() == []
