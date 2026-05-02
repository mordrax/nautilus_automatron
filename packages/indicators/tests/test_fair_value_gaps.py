"""Tests for FairValueGapDetector — lifecycle-tracked levels."""

from indicators.key_levels.detectors.fair_value_gaps import FairValueGapDetector
from indicators.key_levels.model import FairValueGapMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar, make_bars_from_closes


def _warmup_bars(count: int = 20) -> list:
    return make_bars_from_closes(
        [100.0] * count,
        spread=0.5,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )


def test_no_levels_before_warmup():
    det = FairValueGapDetector(atr_period=14)
    det.update(make_bar(100.0, 101.0, 99.0, 100.0))
    assert det.levels() == []


def test_bullish_fvg_detected():
    """3-bar pattern: bar2.low > bar0.high → bullish FVG."""
    bars = _warmup_bars(20)
    idx = len(bars)
    # bar0: high = 100.5
    bars.append(make_bar(100.0, 100.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # bar1: middle bar
    bars.append(make_bar(101.0, 105.0, 100.5, 104.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # bar2: low = 105.0 > bar0.high (100.5) → gap of 4.5 > 0.5*ATR
    bars.append(make_bar(106.0, 108.0, 105.0, 107.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = FairValueGapDetector(atr_period=14, min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    bullish = [
        lv for lv in levels
        if isinstance(lv.meta, FairValueGapMeta) and lv.meta.gap_side == "bullish"
    ]
    assert bullish, "expected a bullish FVG"
    lv = bullish[0]
    assert lv.source == "fair_value_gap"
    assert lv.meta.side == "low"
    assert lv.meta.gap_size > 0
    assert lv.zone_upper is not None and lv.zone_lower is not None
    assert lv.zone_upper > lv.zone_lower


def test_bearish_fvg_detected():
    bars = _warmup_bars(20)
    idx = len(bars)
    # bar0: low = 99.5
    bars.append(make_bar(100.0, 100.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(99.0, 99.5, 95.0, 96.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # bar2: high = 94.0 < bar0.low (99.5) → bearish gap of 5.5
    bars.append(make_bar(94.0, 94.0, 90.0, 91.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = FairValueGapDetector(atr_period=14, min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    bearish = [
        lv for lv in levels
        if isinstance(lv.meta, FairValueGapMeta) and lv.meta.gap_side == "bearish"
    ]
    assert bearish, "expected a bearish FVG"
    assert bearish[0].meta.side == "high"


def test_fvg_filled_finalizes_level():
    """A bullish FVG is finalized once price fills the gap."""
    bars = _warmup_bars(20)
    idx = len(bars)
    bars.append(make_bar(100.0, 100.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(101.0, 105.0, 100.5, 104.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(106.0, 108.0, 105.0, 107.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # Fill back through the gap.
    bars.append(make_bar(107.0, 107.0, 100.0, 100.5,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = FairValueGapDetector(atr_period=14, min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    bullish = [
        lv for lv in levels
        if isinstance(lv.meta, FairValueGapMeta) and lv.meta.gap_side == "bullish"
    ]
    finalized = [lv for lv in bullish if lv.end_ts is not None]
    assert finalized, "expected filled FVG to be finalized"
    assert finalized[0].meta.fill_percentage >= 1.0


def test_active_fvg_has_no_end_ts():
    bars = _warmup_bars(20)
    idx = len(bars)
    bars.append(make_bar(100.0, 100.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(101.0, 105.0, 100.5, 104.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(106.0, 108.0, 105.0, 107.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = FairValueGapDetector(atr_period=14, min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_reset_clears_state():
    det = FairValueGapDetector(atr_period=14)
    for bar in _warmup_bars(25):
        det.update(bar)
    det.reset()
    assert det.levels() == []
