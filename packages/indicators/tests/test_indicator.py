"""Tests for KeyLevelIndicator — NautilusTrader integration."""

import math

import pytest

from indicators.key_levels.indicator import KeyLevelIndicator
from indicators.key_levels.model import KeyLevel, SwingClusterMeta
from tests.helpers.bar_factory import make_bar


class FakeDetector:
    """A trivial detector for testing the indicator shell."""

    def __init__(self, fixed_levels: list[KeyLevel] | None = None, warmup: int = 0):
        self._fixed_levels = fixed_levels or []
        self._warmup = warmup
        self._bar_count = 0

    @property
    def name(self):
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return self._warmup

    def update(self, bar) -> None:
        self._bar_count += 1

    def levels(self) -> list[KeyLevel]:
        if self._bar_count >= self._warmup:
            return list(self._fixed_levels)
        return []

    def reset(self) -> None:
        self._bar_count = 0


def _make_level(price: float, strength: float) -> KeyLevel:
    return KeyLevel(
        price=price,
        strength=strength,
        bounce_count=1,
        first_seen_ts=0,
        last_touched_ts=0,
        zone_upper=price + 0.5,
        zone_lower=price - 0.5,
        source="swing_cluster",
        meta=SwingClusterMeta(cluster_radius=0.5, pivot_indices=(0,)),
    )


def test_indicator_not_initialized_before_warmup():
    detector = FakeDetector(warmup=3)
    indicator = KeyLevelIndicator(detectors=[detector])
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    indicator.handle_bar(bar)
    assert not indicator.initialized


def test_indicator_initialized_after_warmup():
    detector = FakeDetector(warmup=2)
    indicator = KeyLevelIndicator(detectors=[detector])
    for i in range(2):
        indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0, ts_ns=i * 1000))
    assert indicator.initialized


def test_indicator_levels_returned():
    levels = [_make_level(100.0, 0.8), _make_level(110.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels) == 2


def test_indicator_levels_sorted_by_strength_desc():
    levels = [_make_level(100.0, 0.3), _make_level(110.0, 0.9), _make_level(105.0, 0.6)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    strengths = [l.strength for l in indicator.levels]
    assert strengths == [0.9, 0.6, 0.3]


def test_nearest_support_by_proximity():
    levels = [_make_level(90.0, 0.9), _make_level(99.0, 0.3)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert indicator.nearest_support == pytest.approx(99.0, abs=0.01)


def test_strongest_support():
    levels = [_make_level(90.0, 0.9), _make_level(99.0, 0.3)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert indicator.strongest_support == pytest.approx(90.0, abs=0.01)


def test_nearest_resistance_by_proximity():
    levels = [_make_level(101.0, 0.3), _make_level(120.0, 0.9)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert indicator.nearest_resistance == pytest.approx(101.0, abs=0.01)


def test_no_support_returns_nan():
    levels = [_make_level(110.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert math.isnan(indicator.nearest_support)
    assert math.isnan(indicator.strongest_support)


def test_levels_by_source():
    levels = [_make_level(100.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels_by_source("swing_cluster")) == 1
    assert len(indicator.levels_by_source("pivot_standard")) == 0


def test_level_count():
    levels = [_make_level(100.0, 0.5), _make_level(110.0, 0.8)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert indicator.level_count == 2.0


def test_max_levels_truncates():
    levels = [_make_level(90.0 + i, 0.1 * i) for i in range(20)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector], max_levels=5)
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert len(indicator.levels) == 5
    # Should keep the 5 strongest
    assert indicator.levels[0].strength == pytest.approx(1.9, abs=0.01)


def test_reset():
    levels = [_make_level(100.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels) == 1
    indicator.reset()
    assert indicator.levels == []
    assert not indicator.initialized
