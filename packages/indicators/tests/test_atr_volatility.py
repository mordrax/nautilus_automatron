"""Tests for AtrVolatilityDetector — lifecycle-tracked levels."""

import math

import pytest

from indicators.key_levels.detectors.atr_volatility import (
    AtrVolatilityDetector,
    _TrackedLevel,
)
from indicators.key_levels.model import AtrVolatilityMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar, make_bars_from_closes


def _stable_warmup_bars(count: int = 20) -> list:
    """Bars with stable prices around 100 for ATR warmup."""
    return make_bars_from_closes(
        [100.0] * count,
        spread=0.5,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )


def test_no_levels_before_atr_ready():
    det = AtrVolatilityDetector(atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.0)
    det.update(bar)
    assert det.levels() == []


def test_levels_emitted_after_warmup():
    det = AtrVolatilityDetector(
        atr_period=14, multipliers=(1.0, 2.0),
        # Don't replace the first bands so we can assert their count.
        band_replacement_atr=100.0,
    )
    for bar in _stable_warmup_bars(20):
        det.update(bar)
    levels = det.levels()
    # 2 multipliers * 2 sides = 4 levels.
    assert len(levels) == 4
    sides = {lvl.meta.side for lvl in levels}
    assert sides == {"high", "low"}
    multipliers = {lvl.meta.multiplier for lvl in levels}
    assert multipliers == {1.0, 2.0}


def test_higher_multiplier_higher_strength():
    det = AtrVolatilityDetector(
        atr_period=14, multipliers=(1.0, 2.0, 3.0),
        band_replacement_atr=100.0,
    )
    for bar in _stable_warmup_bars(20):
        det.update(bar)
    levels = det.levels()
    by_mult: dict[float, float] = {}
    for lvl in levels:
        assert isinstance(lvl.meta, AtrVolatilityMeta)
        by_mult[lvl.meta.multiplier] = lvl.strength
    sorted_mults = sorted(by_mult.keys())
    for i in range(1, len(sorted_mults)):
        assert by_mult[sorted_mults[i]] >= by_mult[sorted_mults[i - 1]]


def test_source_and_meta_types():
    det = AtrVolatilityDetector(atr_period=14, band_replacement_atr=100.0)
    for bar in _stable_warmup_bars(20):
        det.update(bar)
    for level in det.levels():
        assert level.source == "atr_volatility"
        assert isinstance(level.meta, AtrVolatilityMeta)
        assert level.meta.atr_value > 0
        assert level.meta.multiplier > 0
        assert level.meta.anchor_price > 0
        assert level.meta.side in ("high", "low")
        assert isinstance(level.meta.touch_count, int)


def test_band_replacement_finalizes_previous_band():
    """When the anchor moves enough, the previous band is finalized and a
    new one emitted."""
    bars = make_bars_from_closes(
        [100.0] * 20 + [120.0] * 5,
        spread=0.5,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )
    det = AtrVolatilityDetector(
        atr_period=14,
        multipliers=(1.0,),
        # Strict replacement — any drift > 0.5 ATR triggers a replacement.
        band_replacement_atr=0.5,
        # Don't break/age out for this test.
        break_atr_multiple=100.0,
        break_consecutive_bars=100,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    # Expect at least one finalized level (end_ts is not None).
    finalized = [lv for lv in levels if lv.end_ts is not None]
    assert finalized, "expected band replacement to finalize at least one level"


def test_break_path_finalizes_level():
    """A run of bars closing far above a high-side band finalizes it."""
    warmup = _stable_warmup_bars(20)
    rally = []
    for i in range(5):
        ts = _BASE_TS + (20 + i) * _1H_NS
        rally.append(make_bar(100.0 + 10 * i, 110.0 + 10 * i,
                              100.0 + 10 * i, 110.0 + 10 * i, ts_ns=ts))
    det = AtrVolatilityDetector(
        atr_period=14,
        multipliers=(1.0,),
        band_replacement_atr=100.0,    # don't replace
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in warmup + rally:
        det.update(bar)
    levels = det.levels()
    high_levels = [lv for lv in levels if lv.meta.side == "high"]
    finalized = [lv for lv in high_levels if lv.end_ts is not None]
    assert finalized, "expected a high-side band to break and finalize"


def test_active_levels_have_no_end_ts():
    det = AtrVolatilityDetector(
        atr_period=14, multipliers=(1.0,),
        band_replacement_atr=100.0,
        break_atr_multiple=100.0,
        break_consecutive_bars=100,
        max_idle_bars=10_000,
    )
    for bar in _stable_warmup_bars(20):
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_deterministic():
    bars = _stable_warmup_bars(20)
    det1 = AtrVolatilityDetector(atr_period=14, band_replacement_atr=100.0)
    det2 = AtrVolatilityDetector(atr_period=14, band_replacement_atr=100.0)
    for bar in bars:
        det1.update(bar)
        det2.update(bar)
    assert det1.levels() == det2.levels()


def test_reset_clears_state():
    det = AtrVolatilityDetector(atr_period=14, band_replacement_atr=100.0)
    for bar in _stable_warmup_bars(20):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []


def test_strength_decay_shape():
    """Bounce count past min_touches drives exponential decay."""
    det = AtrVolatilityDetector(
        atr_period=14,
        multipliers=(1.0,),
        strength_decay_k=3.0,
        min_touches=1,
    )
    expected_bounces = [1, 4, 9]
    det._tracked.clear()
    det._tracked.extend([
        _TrackedLevel(
            id=i,
            side="high",
            centroid=100.0,
            members=[100.0],
            member_ts=[_BASE_TS],
            start_ts=_BASE_TS,
            end_ts=None,
            bounce_count=count,
            touch_count=0,
            last_touch_ts=_BASE_TS,
            bars_through=0,
            multiplier=1.0,
            anchor_price=100.0,
            atr_at_emit=1.0,
        )
        for i, count in enumerate(expected_bounces)
    ])
    levels = det.levels()
    by_count = {lvl.bounce_count: lvl.strength for lvl in levels}
    # mult/max_multiplier = 1.0 here, so strength == decay
    assert by_count[1] == pytest.approx(math.exp(0.0), abs=1e-6)
    assert by_count[4] == pytest.approx(math.exp(-3.0 / 3.0), abs=1e-6)
    assert by_count[9] == pytest.approx(math.exp(-8.0 / 3.0), abs=1e-6)
