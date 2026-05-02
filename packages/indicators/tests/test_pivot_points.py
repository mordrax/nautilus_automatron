"""Tests for PivotPointDetector — lifecycle-tracked period-anchored S/R levels."""

from indicators.key_levels.detectors.pivot_points import (
    PivotPointDetector,
    PivotVariant,
)
from indicators.key_levels.model import PivotPointMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_period_bars(period_bars: int, count_periods: int = 3) -> list:
    """Build `count_periods` periods of `period_bars` bars each, with a
    rising-then-falling pattern so that successive periods produce different
    pivots (and break checks fire as price moves between periods)."""
    bars = []
    idx = 0
    base_prices: list[float] = []
    for p in range(count_periods):
        # Each period oscillates around a different center to force different
        # pivots and to give bars enough range for ATR.
        center = 100.0 + p * 5.0
        for i in range(period_bars):
            phase = i % 4
            if phase == 0:
                o, h, lo, c = center, center + 2.0, center - 1.0, center + 1.0
            elif phase == 1:
                o, h, lo, c = center + 1.0, center + 3.0, center, center + 2.0
            elif phase == 2:
                o, h, lo, c = center + 2.0, center + 2.5, center - 0.5, center + 0.5
            else:
                o, h, lo, c = center + 0.5, center + 1.5, center - 1.5, center
            ts = _BASE_TS + idx * _1H_NS
            bars.append(make_bar(o, h, lo, c, ts_ns=ts))
            idx += 1
            base_prices.append(c)
    return bars


def test_no_levels_before_first_period_completes():
    det = PivotPointDetector(variant="standard", period_bars=24, atr_period=14)
    bars = _make_period_bars(period_bars=24, count_periods=1)
    # Feed only 23 bars (not enough for first period to complete).
    for bar in bars[:23]:
        det.update(bar)
    assert det.levels() == []


def test_emits_levels_after_first_period():
    det = PivotPointDetector(variant="standard", period_bars=24, atr_period=14)
    bars = _make_period_bars(period_bars=24, count_periods=1)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert levels
    # Standard variant: 5 levels (PP, R1, S1, R2, S2).
    assert len(levels) == 5
    names = {lvl.meta.level_name for lvl in levels}
    assert names == {"PP", "R1", "S1", "R2", "S2"}


def test_source_and_meta_types():
    det = PivotPointDetector(variant="standard", period_bars=24, atr_period=14)
    bars = _make_period_bars(period_bars=24, count_periods=1)
    for bar in bars:
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "pivot_standard"
        assert isinstance(lvl.meta, PivotPointMeta)
        assert lvl.meta.variant == "standard"
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)


def test_each_variant_has_correct_source():
    variants: list[tuple[PivotVariant, str, int]] = [
        ("standard", "pivot_standard", 5),
        ("fibonacci", "pivot_fibonacci", 7),
        ("camarilla", "pivot_camarilla", 9),
        ("woodie", "pivot_woodie", 5),
        ("demark", "pivot_demark", 3),
    ]
    bars = _make_period_bars(period_bars=24, count_periods=1)
    for variant, expected_source, expected_count in variants:
        det = PivotPointDetector(variant=variant, period_bars=24, atr_period=14)
        for bar in bars:
            det.update(bar)
        levels = det.levels()
        assert all(lv.source == expected_source for lv in levels), variant
        assert len(levels) == expected_count, variant


def test_new_period_finalizes_previous_set():
    det = PivotPointDetector(
        variant="standard",
        period_bars=12,
        atr_period=5,
        # Don't break/age out via lifecycle for this test.
        break_atr_multiple=100.0,
        break_consecutive_bars=100,
        max_idle_bars=10_000,
    )
    bars = _make_period_bars(period_bars=12, count_periods=2)
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    # After 2 periods complete, the first set should be finalized; the second
    # set is still active.
    finalized = [lv for lv in levels if lv.end_ts is not None]
    active = [lv for lv in levels if lv.end_ts is None]
    assert finalized, "expected first period's levels to be finalized"
    assert active, "expected second period's levels to be active"


def test_break_path_within_period_finalizes_level():
    """A sustained close far beyond a level should break it."""
    bars = _make_period_bars(period_bars=12, count_periods=1)
    # After period closes, push a strong rally past R2.
    idx = len(bars)
    for p in [120.0, 140.0, 160.0, 180.0]:
        ts = _BASE_TS + idx * _1H_NS
        bars.append(make_bar(p - 5.0, p + 1.0, p - 6.0, p, ts_ns=ts))
        idx += 1
    det = PivotPointDetector(
        variant="standard",
        period_bars=12,
        atr_period=5,
        break_atr_multiple=0.5,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected at least one pivot level to break"


def test_deterministic():
    bars = _make_period_bars(period_bars=12, count_periods=2)
    a = PivotPointDetector(variant="standard", period_bars=12, atr_period=5)
    b = PivotPointDetector(variant="standard", period_bars=12, atr_period=5)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = PivotPointDetector(variant="standard", period_bars=12, atr_period=5)
    for bar in _make_period_bars(period_bars=12, count_periods=2):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []


def test_levels_in_data_range():
    det = PivotPointDetector(variant="standard", period_bars=12, atr_period=5)
    bars = _make_period_bars(period_bars=12, count_periods=2)
    for bar in bars:
        det.update(bar)
    first = bars[0].ts_event
    last = bars[-1].ts_event
    for lv in det.levels():
        assert first <= lv.start_ts <= last
        if lv.end_ts is not None:
            assert lv.start_ts <= lv.end_ts <= last
