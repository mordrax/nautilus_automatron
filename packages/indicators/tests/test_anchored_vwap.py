"""Tests for AnchoredVwapDetector — VWAP-snapshot levels per anchor."""

from indicators.key_levels.detectors.anchored_vwap import AnchoredVwapDetector
from indicators.key_levels.model import AnchoredVwapMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_swing_bars(swing_count: int = 3, period: int = 5) -> list:
    """Build OHLCV bars with `swing_count` alternating fractal swings."""
    bars: list = []
    centers = [100.0, 110.0, 95.0, 115.0, 90.0, 120.0]
    centers = centers[:swing_count]

    idx = 0
    base = 100.0
    for c_i, target in enumerate(centers):
        going_up = target > base
        for j in range(period):
            frac = (j + 1) / (period + 1)
            price = base + (target - base) * frac
            o = price - 0.3
            cl = price + 0.3
            h = max(o, cl) + 0.5
            lo = min(o, cl) - 0.5
            bars.append(make_bar(o, h, lo, cl,
                                 volume=100.0, ts_ns=_BASE_TS + idx * _1H_NS))
            idx += 1
        if going_up:
            bars.append(make_bar(target - 0.3, target + 1.0, target - 0.5, target,
                                 volume=120.0, ts_ns=_BASE_TS + idx * _1H_NS))
        else:
            bars.append(make_bar(target + 0.3, target + 0.5, target - 1.0, target,
                                 volume=120.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
        base = target

    last_dir = -1 if centers[-1] > centers[-2] else 1
    for j in range(period):
        price = base + last_dir * (j + 1) * 0.5
        o = price - 0.3
        cl = price + 0.3
        h = max(o, cl) + 0.5
        lo = min(o, cl) - 0.5
        bars.append(make_bar(o, h, lo, cl,
                             volume=100.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    return bars


def test_no_levels_before_warmup():
    det = AnchoredVwapDetector(swing_period=5, atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_levels_emit_after_anchor_forms():
    det = AnchoredVwapDetector(
        swing_period=5, atr_period=10,
        # Don't replace, break, or age out for this assertion.
        vwap_drift_atr=100.0,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _make_swing_bars(swing_count=3, period=5):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1


def test_source_and_meta_types():
    det = AnchoredVwapDetector(
        swing_period=5, atr_period=10,
        vwap_drift_atr=100.0,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _make_swing_bars(swing_count=3, period=5):
        det.update(bar)
    for level in det.levels():
        assert level.source == "anchored_vwap"
        assert isinstance(level.meta, AnchoredVwapMeta)
        assert level.meta.anchor_type in (
            "swing_high", "swing_low", "gap", "volume_spike",
        )
        assert level.meta.cumulative_volume > 0
        assert level.meta.side in ("high", "low")
        assert isinstance(level.meta.touch_count, int)


def test_vwap_drift_replaces_level():
    """When the running VWAP drifts past `vwap_drift_atr * ATR`, finalize the
    old level and emit a fresh one."""
    det = AnchoredVwapDetector(
        swing_period=5, atr_period=10,
        vwap_drift_atr=0.1,        # very tight drift threshold
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _make_swing_bars(swing_count=3, period=5):
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected drift to finalize at least one level"


def test_break_finalizes_level():
    bars = _make_swing_bars(swing_count=3, period=5)
    last_ts = bars[-1].ts_event
    for i in range(5):
        ts = last_ts + (i + 1) * _1H_NS
        bars.append(make_bar(50, 52, 40, 41, volume=100.0, ts_ns=ts))
    det = AnchoredVwapDetector(
        swing_period=5, atr_period=10,
        vwap_drift_atr=100.0,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected break to finalize at least one level"


def test_deterministic():
    bars = _make_swing_bars(swing_count=3, period=5)
    a = AnchoredVwapDetector(swing_period=5, atr_period=10)
    b = AnchoredVwapDetector(swing_period=5, atr_period=10)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = AnchoredVwapDetector(
        swing_period=5, atr_period=10,
        vwap_drift_atr=100.0,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _make_swing_bars(swing_count=3, period=5):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []
