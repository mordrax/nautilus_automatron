"""Tests for DarvasBoxDetector — lifecycle-tracked levels."""

from indicators.key_levels.detectors.darvas_box import DarvasBoxDetector
from indicators.key_levels.model import DarvasBoxMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _build_box_bars() -> list:
    """20 bars rising to a peak, then 3+ bars consolidating below it."""
    bars: list = []
    # 20 bars climbing — last one sets the peak.
    for i in range(20):
        price = 100.0 + i * 0.5
        bars.append(make_bar(
            price - 0.1, price + 0.5, price - 0.5, price + 0.3,
            ts_ns=_BASE_TS + i * _1H_NS,
        ))
    # Bar at index 19 must be the highest. Replace it with a clear peak.
    peak_ts = _BASE_TS + 19 * _1H_NS
    bars[-1] = make_bar(109.5, 112.0, 109.0, 111.0, ts_ns=peak_ts)
    # 4 bars consolidating well below 112 (no new high).
    for j in range(5):
        ts = _BASE_TS + (20 + j) * _1H_NS
        bars.append(make_bar(109.0, 110.5, 108.0, 109.5, ts_ns=ts))
    return bars


def test_no_levels_before_lookback():
    det = DarvasBoxDetector(lookback_period=20)
    det.update(make_bar(100.0, 101.0, 99.0, 100.0))
    assert det.levels() == []


def test_box_confirmed_after_consolidation():
    bars = _build_box_bars()
    det = DarvasBoxDetector(lookback_period=20, confirmation_bars=3,
                            atr_period=14)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert levels, "expected a confirmed Darvas box"
    lv = levels[0]
    assert lv.source == "darvas_box"
    assert isinstance(lv.meta, DarvasBoxMeta)
    assert lv.meta.confirmed is True
    assert lv.zone_upper is not None and lv.zone_lower is not None
    assert lv.zone_upper > lv.zone_lower


def test_box_breakout_finalizes_level():
    bars = _build_box_bars()
    idx = len(bars)
    # Strong breakout above box top.
    for j in range(5):
        ts = _BASE_TS + (idx + j) * _1H_NS
        bars.append(make_bar(120.0 + j, 125.0 + j, 119.5 + j, 124.5 + j,
                             ts_ns=ts))

    det = DarvasBoxDetector(lookback_period=20, confirmation_bars=3,
                            atr_period=14, break_atr_multiple=1.0)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    finalized = [lv for lv in levels if lv.end_ts is not None]
    assert finalized, "expected box to be finalized by breakout"


def test_active_box_has_no_end_ts():
    bars = _build_box_bars()
    det = DarvasBoxDetector(lookback_period=20, confirmation_bars=3,
                            atr_period=14)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_reset_clears_state():
    bars = _build_box_bars()
    det = DarvasBoxDetector(lookback_period=20, confirmation_bars=3,
                            atr_period=14)
    for bar in bars:
        det.update(bar)
    det.reset()
    assert det.levels() == []


def test_meta_side_set():
    bars = _build_box_bars()
    det = DarvasBoxDetector(lookback_period=20, confirmation_bars=3,
                            atr_period=14)
    for bar in bars:
        det.update(bar)
    for lv in det.levels():
        assert lv.meta.side in ("high", "low")
        assert isinstance(lv.meta.touch_count, int)
