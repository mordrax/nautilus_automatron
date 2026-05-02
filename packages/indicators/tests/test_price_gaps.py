"""Tests for PriceGapDetector — lifecycle-tracked levels."""

from indicators.key_levels.detectors.price_gaps import PriceGapDetector
from indicators.key_levels.model import PriceGapMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar, make_bars_from_closes


def _warmup_bars(count: int = 25) -> list:
    return make_bars_from_closes(
        [100.0] * count,
        spread=0.5,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )


def test_no_levels_before_warmup():
    det = PriceGapDetector(atr_period=14, volume_period=20)
    det.update(make_bar(100.0, 101.0, 99.0, 100.0))
    assert det.levels() == []


def test_gap_up_detected():
    bars = _warmup_bars(25)
    idx = len(bars)
    # Gap up: prev high = 100.5, next bar low = 105.0 → gap = 4.5
    bars.append(make_bar(106.0, 108.0, 105.0, 107.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = PriceGapDetector(atr_period=14, volume_period=20,
                           min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    assert any(
        isinstance(lv.meta, PriceGapMeta) for lv in levels
    ), "expected a price gap"
    lv = levels[0]
    assert lv.source == "price_gap"
    assert lv.meta.side == "low"  # gap-up sits below price
    assert lv.zone_upper is not None and lv.zone_lower is not None


def test_gap_down_detected():
    bars = _warmup_bars(25)
    idx = len(bars)
    # Gap down: prev low = 99.5, next bar high = 95.0
    bars.append(make_bar(94.0, 95.0, 90.0, 91.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = PriceGapDetector(atr_period=14, volume_period=20,
                           min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    assert levels
    lv = levels[0]
    assert lv.meta.side == "high"


def test_gap_filled_finalizes_level():
    bars = _warmup_bars(25)
    idx = len(bars)
    bars.append(make_bar(106.0, 108.0, 105.0, 107.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # Fill all the way back down through the gap zone.
    bars.append(make_bar(107.0, 107.0, 100.0, 100.5,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = PriceGapDetector(atr_period=14, volume_period=20,
                           min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    finalized = [lv for lv in levels if lv.end_ts is not None]
    assert finalized
    assert finalized[0].meta.fill_percentage >= 1.0


def test_volume_classification():
    """Breakaway = high vol; exhaustion = low vol."""
    bars = _warmup_bars(25)
    idx = len(bars)
    # High-volume gap up.
    bars.append(make_bar(
        106.0, 108.0, 105.0, 107.0,
        volume=500.0,  # 5x default 100
        ts_ns=_BASE_TS + idx * _1H_NS,
    ))

    det = PriceGapDetector(atr_period=14, volume_period=20,
                           min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert levels
    assert levels[0].meta.gap_type == "breakaway"


def test_reset_clears_state():
    det = PriceGapDetector(atr_period=14, volume_period=20)
    for bar in _warmup_bars(25):
        det.update(bar)
    det.reset()
    assert det.levels() == []


def test_active_gap_has_no_end_ts():
    bars = _warmup_bars(25)
    idx = len(bars)
    bars.append(make_bar(106.0, 108.0, 105.0, 107.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    det = PriceGapDetector(atr_period=14, volume_period=20,
                           min_gap_atr_multiple=0.5)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)
