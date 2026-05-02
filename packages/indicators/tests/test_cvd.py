"""Tests for CvdDetector — Cumulative Volume Delta pivot levels."""

from indicators.key_levels.detectors.cvd import CvdDetector
from indicators.key_levels.model import CvdMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_cvd_bars() -> list:
    """Bars whose buy/sell volume estimate produces clear CVD swings.

    Bullish bars (close near high) push CVD up; bearish bars (close near low)
    push CVD down. We alternate clusters to create CVD pivots.
    """
    bars: list = []
    idx = 0

    def push(o, h, lo, cl, vol=100.0):
        nonlocal idx
        bars.append(make_bar(o, h, lo, cl, volume=vol,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    # Cluster 1: 8 strongly-bullish bars (close = high) → CVD rises.
    base = 100.0
    for i in range(8):
        o = base + i * 0.2
        h = o + 1.0
        lo = o - 0.1
        cl = h
        push(o, h, lo, cl)

    # Cluster 2: 8 strongly-bearish bars (close = low) → CVD falls.
    base2 = bars[-1].close.as_double()
    for i in range(8):
        o = base2 - i * 0.2
        h = o + 0.1
        lo = o - 1.0
        cl = lo
        push(o, h, lo, cl)

    # Cluster 3: 8 strongly-bullish bars again.
    base3 = bars[-1].close.as_double()
    for i in range(8):
        o = base3 + i * 0.2
        h = o + 1.0
        lo = o - 0.1
        cl = h
        push(o, h, lo, cl)

    # Cluster 4: 8 bearish.
    base4 = bars[-1].close.as_double()
    for i in range(8):
        o = base4 - i * 0.2
        h = o + 0.1
        lo = o - 1.0
        cl = lo
        push(o, h, lo, cl)

    return bars


def test_no_levels_before_window_full():
    det = CvdDetector(swing_period=5, atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_levels_emit_for_cvd_pivots():
    det = CvdDetector(swing_period=5, atr_period=10)
    for bar in _make_cvd_bars():
        det.update(bar)
    assert len(det.levels()) >= 1


def test_source_and_meta_types():
    det = CvdDetector(swing_period=5, atr_period=10)
    for bar in _make_cvd_bars():
        det.update(bar)
    for level in det.levels():
        assert level.source == "cvd"
        assert isinstance(level.meta, CvdMeta)
        assert level.meta.divergence in ("bullish", "bearish", "none")
        assert level.meta.side in ("high", "low")
        assert isinstance(level.meta.touch_count, int)


def test_active_levels_have_no_end_ts():
    det = CvdDetector(
        swing_period=5, atr_period=10,
        break_atr_multiple=100.0, max_idle_bars=10_000,
    )
    for bar in _make_cvd_bars():
        det.update(bar)
    assert any(lv.end_ts is None for lv in det.levels())


def test_break_finalizes_level():
    bars = _make_cvd_bars()
    last_ts = bars[-1].ts_event
    last_close = bars[-1].close.as_double()
    for i in range(5):
        ts = last_ts + (i + 1) * _1H_NS
        bars.append(make_bar(
            last_close - 20 - i * 5,
            last_close - 18 - i * 5,
            last_close - 30 - i * 5,
            last_close - 30 - i * 5,
            volume=100.0, ts_ns=ts,
        ))
    det = CvdDetector(
        swing_period=5, atr_period=10,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected at least one CVD level to finalize on break"


def test_deterministic():
    bars = _make_cvd_bars()
    a = CvdDetector(swing_period=5, atr_period=10)
    b = CvdDetector(swing_period=5, atr_period=10)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = CvdDetector(swing_period=5, atr_period=10)
    for bar in _make_cvd_bars():
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []
