"""Tests for KeyLevelIndicator — NautilusTrader integration."""

import math

import pytest

from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.indicator import KeyLevelIndicator
from indicators.key_levels.model import EqualHighsLowsMeta, KeyLevel
from tests.helpers.bar_factory import make_bar, make_bars_from_ohlcv


class FakeDetector:
    """A trivial detector for testing the indicator shell."""

    def __init__(
        self,
        fixed_levels: list[KeyLevel] | None = None,
        warmup: int = 0,
        name: str = "equal_highs_lows",
    ):
        self._fixed_levels = fixed_levels or []
        self._warmup = warmup
        self._bar_count = 0
        self._name = name

    @property
    def name(self):
        return self._name

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


def _make_level(
    price: float,
    strength: float,
    end_ts: int | None = None,
    side: str = "high",
) -> KeyLevel:
    return KeyLevel(
        price=price,
        strength=strength,
        start_ts=0,
        end_ts=end_ts,
        source="equal_highs_lows",
        bounce_count=2,
        zone_upper=price + 0.5,
        zone_lower=price - 0.5,
        meta=EqualHighsLowsMeta(
            touch_prices=(price - 0.1, price + 0.1),
            side=side,  # type: ignore[arg-type]
            touch_count=2,
        ),
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
    levels = [
        _make_level(100.0, 0.3),
        _make_level(110.0, 0.9),
        _make_level(105.0, 0.6),
    ]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    strengths = [lvl.strength for lvl in indicator.levels]
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
    assert len(indicator.levels_by_source("equal_highs_lows")) == 1
    assert len(indicator.levels_by_source("pivot_standard")) == 0


def test_level_count():
    levels = [_make_level(100.0, 0.5), _make_level(110.0, 0.8)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert indicator.level_count == 2.0


def test_max_levels_truncates():
    # Strengths must be in [0, 1] for the new model; spread them to test sort.
    levels = [_make_level(90.0 + i, i / 20.0) for i in range(20)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector], max_levels=5)
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert len(indicator.levels) == 5
    # Should keep the 5 strongest
    assert indicator.levels[0].strength == pytest.approx(0.95, abs=0.01)


def test_reset():
    levels = [_make_level(100.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels) == 1
    indicator.reset()
    assert indicator.levels == []
    assert not indicator.initialized


# -- Lifecycle-aware scalar summaries --


def test_scalar_summaries_ignore_finalized_levels():
    """Levels with end_ts set are excluded from nearest_support/resistance."""
    active_below = _make_level(95.0, 0.4, end_ts=None)
    finalized_below = _make_level(98.0, 0.9, end_ts=12345)  # closer but ended
    detector = FakeDetector(
        fixed_levels=[active_below, finalized_below], warmup=0,
    )
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))

    # The finalized closer level must be ignored.
    assert indicator.nearest_support == pytest.approx(95.0, abs=0.01)


# -- End-to-end with the real EqualHighsLows detector --


def _make_realistic_bars():
    """Bars with clear repeated swing highs near 110 and lows near 90."""
    data = []
    # 14 warmup bars around 100
    for _ in range(14):
        data.append((100.0, 102.0, 98.0, 100.0, 100.0))

    # Two swing highs at ~110 and two swing lows at ~90
    for cycle in range(3):
        data.extend([
            (100.0, 102.0, 98.0, 101.0, 100.0),
            (101.0, 106.0, 100.0, 105.0, 100.0),
            (105.0, 110.0, 104.0, 108.0, 100.0),  # swing high
            (108.0, 108.0, 100.0, 102.0, 100.0),
            (102.0, 103.0, 95.0, 96.0, 100.0),
            (96.0, 97.0, 92.0, 93.0, 100.0),
            (93.0, 94.0, 90.0, 91.0, 100.0),       # swing low
            (91.0, 96.0, 91.0, 95.0, 100.0),
            (95.0, 100.0, 94.0, 99.0, 100.0),
        ])

    return make_bars_from_ohlcv(data)


def test_end_to_end_with_real_detector():
    """Full integration with the migrated EqualHighsLowsDetector."""
    indicator = KeyLevelIndicator(detectors=[
        EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.8, atr_period=14),
    ])
    bars = _make_realistic_bars()
    for bar in bars:
        indicator.handle_bar(bar)

    assert len(indicator.levels) > 0

    for level in indicator.levels:
        assert 0.0 <= level.strength <= 1.0
        assert level.bounce_count >= 0
        # start_ts/end_ts ordering when ended
        if level.end_ts is not None:
            assert level.start_ts <= level.end_ts
        # zone_lower <= price <= zone_upper when zone is populated
        if level.zone_lower is not None and level.zone_upper is not None:
            assert level.zone_lower <= level.price <= level.zone_upper

    assert not math.isnan(indicator.level_count)
    assert indicator.level_count > 0
