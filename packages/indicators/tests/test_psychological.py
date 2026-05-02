"""Tests for PsychologicalLevelDetector — lifecycle-tracked round-number levels."""

import math

import pytest

from indicators.key_levels.detectors.psychological import (
    PsychologicalLevelDetector,
    _TrackedLevel,
)
from indicators.key_levels.model import PsychologicalMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar, make_bars_from_closes


_DEFAULT_TIERS = {"major": 100.0, "minor": 50.0, "micro": 25.0}


def _stable_warmup_bars(count: int = 20, price: float = 1075.0) -> list:
    return make_bars_from_closes(
        [price] * count,
        spread=0.5,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )


def test_no_levels_before_atr_ready():
    det = PsychologicalLevelDetector(
        tier_steps=_DEFAULT_TIERS, atr_period=14, range_levels=2,
    )
    bar = make_bar(1075.0, 1080.0, 1070.0, 1075.0)
    det.update(bar)
    assert det.levels() == []


def test_emits_round_levels_around_price():
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0},
        range_levels=2,
        atr_period=14,
    )
    for bar in _stable_warmup_bars(20, price=1075.0):
        det.update(bar)
    levels = det.levels()
    prices = sorted({lv.price for lv in levels})
    # math.floor(1075/100)*100 = 1000, then i in [-2..2] -> 800..1200.
    assert prices == [800.0, 900.0, 1000.0, 1100.0, 1200.0]


def test_source_and_meta_types():
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0},
        range_levels=1,
        atr_period=14,
    )
    for bar in _stable_warmup_bars(20, price=1075.0):
        det.update(bar)
    for level in det.levels():
        assert level.source == "psychological"
        assert isinstance(level.meta, PsychologicalMeta)
        assert level.meta.tier in ("major", "minor", "micro")
        assert level.meta.side in ("high", "low")
        assert isinstance(level.meta.touch_count, int)


def test_break_path_finalizes_level():
    """A sustained close above a high-side level should break it."""
    warmup = _stable_warmup_bars(20, price=950.0)
    rally = []
    for i, p in enumerate([1010.0, 1050.0, 1100.0, 1150.0, 1200.0, 1250.0]):
        ts = _BASE_TS + (20 + i) * _1H_NS
        rally.append(make_bar(p - 5.0, p + 1.0, p - 6.0, p, ts_ns=ts))
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0},
        range_levels=2,
        atr_period=14,
        break_atr_multiple=0.5,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in warmup + rally:
        det.update(bar)
    levels = det.levels()
    finalized = [lv for lv in levels if lv.end_ts is not None]
    assert finalized, "expected at least one psychological level to break"


def test_active_levels_have_no_end_ts():
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0},
        range_levels=1,
        atr_period=14,
        break_atr_multiple=100.0,
        break_consecutive_bars=100,
    )
    for bar in _stable_warmup_bars(20, price=1075.0):
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_levels_in_data_range():
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0},
        range_levels=1,
        atr_period=14,
    )
    bars = _stable_warmup_bars(20, price=1075.0)
    for bar in bars:
        det.update(bar)
    first = bars[0].ts_event
    last = bars[-1].ts_event
    for lv in det.levels():
        assert first <= lv.start_ts <= last
        if lv.end_ts is not None:
            assert lv.start_ts <= lv.end_ts <= last


def test_deterministic():
    bars = _stable_warmup_bars(20, price=1075.0)
    a = PsychologicalLevelDetector(tier_steps=_DEFAULT_TIERS, range_levels=2)
    b = PsychologicalLevelDetector(tier_steps=_DEFAULT_TIERS, range_levels=2)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = PsychologicalLevelDetector(
        tier_steps=_DEFAULT_TIERS, range_levels=2, atr_period=14,
    )
    for bar in _stable_warmup_bars(20, price=1075.0):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []


def test_strength_decay_shape():
    """Strength = base_strength * exp(-(bounces - min_touches) / k)."""
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0},
        range_levels=1,
        atr_period=14,
        strength_decay_k=3.0,
        min_touches=1,
    )
    expected = [1, 4, 9]
    det._tracked.clear()
    det._tracked.extend([
        _TrackedLevel(
            id=i,
            side="high",
            centroid=1000.0,
            members=[1000.0],
            member_ts=[_BASE_TS],
            start_ts=_BASE_TS,
            end_ts=None,
            bounce_count=count,
            touch_count=0,
            last_touch_ts=_BASE_TS,
            bars_through=0,
            tier="major",
            round_value=1000.0,
            base_strength=1.0,
        )
        for i, count in enumerate(expected)
    ])
    levels = det.levels()
    by_count = {lvl.bounce_count: lvl.strength for lvl in levels}
    assert by_count[1] == pytest.approx(1.0, abs=1e-6)
    assert by_count[4] == pytest.approx(math.exp(-3.0 / 3.0), abs=1e-6)
    assert by_count[9] == pytest.approx(math.exp(-8.0 / 3.0), abs=1e-6)
