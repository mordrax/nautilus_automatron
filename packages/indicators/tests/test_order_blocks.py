"""Tests for OrderBlockDetector — lifecycle-tracked levels."""

from indicators.key_levels.detectors.order_blocks import OrderBlockDetector
from indicators.key_levels.model import OrderBlockMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar, make_bars_from_closes


def _stable_warmup_bars(count: int = 20) -> list:
    return make_bars_from_closes(
        [100.0] * count,
        spread=0.5,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )


def test_no_levels_before_atr_ready():
    det = OrderBlockDetector(atr_period=14)
    det.update(make_bar(100.0, 101.0, 99.0, 100.0))
    assert det.levels() == []


def test_bullish_order_block_detected():
    """A strong bullish displacement after a bearish candle creates a bullish OB."""
    bars = _stable_warmup_bars(20)
    idx = len(bars)
    # One bearish candle (the order block).
    bars.append(make_bar(102.0, 102.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # Strong bullish displacement (body ~10, ATR ~1 → 10x displacement).
    bars.append(make_bar(100.0, 110.5, 100.0, 110.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    bullish = [
        lv for lv in levels
        if isinstance(lv.meta, OrderBlockMeta) and lv.meta.block_side == "bullish"
    ]
    assert bullish, "expected at least one bullish order block"
    lv = bullish[0]
    assert lv.source == "order_block"
    assert lv.zone_upper is not None and lv.zone_lower is not None
    assert lv.zone_upper > lv.zone_lower
    assert lv.meta.side == "low"
    assert lv.meta.displacement_atr_multiple > 2.0


def test_bearish_order_block_detected():
    bars = _stable_warmup_bars(20)
    idx = len(bars)
    # One bullish candle (the order block).
    bars.append(make_bar(98.0, 100.5, 97.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # Strong bearish displacement.
    bars.append(make_bar(100.0, 100.0, 89.5, 90.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    bearish = [
        lv for lv in levels
        if isinstance(lv.meta, OrderBlockMeta) and lv.meta.block_side == "bearish"
    ]
    assert bearish, "expected a bearish order block"
    assert bearish[0].meta.side == "high"


def test_active_order_block_has_no_end_ts():
    bars = _stable_warmup_bars(20)
    idx = len(bars)
    bars.append(make_bar(102.0, 102.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(100.0, 110.5, 100.0, 110.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_order_block_mitigated_by_full_traversal():
    """Bullish OB ends when price closes below the zone after touching it."""
    bars = _stable_warmup_bars(20)
    idx = len(bars)
    # Bearish OB.
    bars.append(make_bar(102.0, 102.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # Strong bullish displacement.
    bars.append(make_bar(100.0, 110.5, 100.0, 110.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    # Price retraces through OB and closes below it.
    bars.append(make_bar(108.0, 108.0, 95.0, 96.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    for bar in bars:
        det.update(bar)

    levels = det.levels()
    bullish = [
        lv for lv in levels
        if isinstance(lv.meta, OrderBlockMeta) and lv.meta.block_side == "bullish"
    ]
    finalized = [lv for lv in bullish if lv.end_ts is not None]
    assert finalized, "expected mitigated OB to be finalized"
    assert finalized[0].meta.mitigation_pct >= 1.0


def test_reset_clears_state():
    bars = _stable_warmup_bars(20)
    idx = len(bars)
    bars.append(make_bar(102.0, 102.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(100.0, 110.5, 100.0, 110.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    for bar in bars:
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []


def test_deterministic():
    bars = _stable_warmup_bars(20)
    idx = len(bars)
    bars.append(make_bar(102.0, 102.5, 99.5, 100.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    bars.append(make_bar(100.0, 110.5, 100.0, 110.0,
                         ts_ns=_BASE_TS + idx * _1H_NS))

    det1 = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    det2 = OrderBlockDetector(atr_period=14, displacement_threshold=2.0)
    for bar in bars:
        det1.update(bar)
        det2.update(bar)
    assert det1.levels() == det2.levels()
