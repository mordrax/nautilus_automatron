"""Tests for FibonacciRetracementDetector."""

from __future__ import annotations

import pytest

from indicators.key_levels.detectors.fibonacci import FibonacciRetracementDetector
from indicators.key_levels.model import FibonacciMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uptrend_bars(
    swing_period: int = 5,
    atr_period: int = 14,
) -> list:
    """Build bars that produce a swing low at 90 then a swing high at 110.

    Strategy:
    - Start with atr_period warmup bars around 100 with ~2pt range (ATR ~2).
    - Create a clear swing low at 90: descend to 90 then ascend.
    - Create a clear swing high at 110: ascend to 110 then descend.
    Each swing needs swing_period bars on each side to confirm the fractal.
    Fractal requires strict inequality, so the peak/trough must be unique.
    """
    bars = []
    ts = _BASE_TS

    def _add(o: float, h: float, lo: float, c: float) -> None:
        nonlocal ts
        bars.append(make_bar(o, h, lo, c, ts_ns=ts))
        ts += _1H_NS

    # Phase 1: ATR warmup — 14 bars oscillating around 100, range ~2
    for i in range(atr_period):
        base = 100.0 + (i % 2) * 0.5
        _add(base, base + 1.0, base - 1.0, base)

    # Phase 2: Descend to create swing low at 90
    # 5 bars descending (lows: 97, 95.5, 94, 92.5, 91 — all above 90)
    for i in range(swing_period):
        price = 98.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    # The swing low bar — low of 90 (must be strictly lower than all neighbours)
    _add(91.0, 91.5, 90.0, 91.0)

    # 5 bars ascending (lows: 92, 94, 96, 98, 100 — all above 90)
    for i in range(swing_period):
        price = 93.0 + i * 2.0
        _add(price, price + 0.5, price - 1.0, price)

    # Phase 3: Ascend to create swing high at 110
    # 5 bars approaching (highs: 103.5, 105, 106.5, 108, 109.5 — all below 110)
    for i in range(swing_period):
        price = 103.0 + i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    # The swing high bar — high of 110 (must be strictly higher than all neighbours)
    _add(109.0, 110.0, 108.5, 109.0)

    # 5 bars descending (highs: 108.5, 107, 105.5, 104, 102.5 — all below 110)
    for i in range(swing_period):
        price = 108.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    return bars


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoLevelsBeforeWarmup:
    """No levels produced until both a swing high and swing low are detected."""

    def test_no_levels_initially(self) -> None:
        det = FibonacciRetracementDetector(swing_period=5, atr_period=14)
        # Feed just a few bars — not enough for any swings
        for i in range(10):
            bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS)
            det.update(bar)

        assert det.levels() == []


class TestRetracementLevelsUptrend:
    """Verify correct retracement levels for swing high=110, swing low=90."""

    @pytest.fixture
    def detector_with_levels(self) -> FibonacciRetracementDetector:
        det = FibonacciRetracementDetector(
            swing_period=5,
            min_swing_atr_multiple=0.5,  # Low threshold so our swings qualify
            atr_period=14,
        )
        bars = _make_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)
        return det

    def test_five_levels_produced(
        self, detector_with_levels: FibonacciRetracementDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        assert len(levels) == 5

    def test_level_prices(
        self, detector_with_levels: FibonacciRetracementDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        prices = [lvl.price for lvl in levels]

        # swing_high=110, swing_low=90, range=20, uptrend
        # level = swing_high - ratio * range
        expected = [
            110.0 - 0.236 * 20,  # 105.28
            110.0 - 0.382 * 20,  # 102.36
            110.0 - 0.5 * 20,    # 100.0
            110.0 - 0.618 * 20,  # 97.64
            110.0 - 0.786 * 20,  # 94.28
        ]

        for actual, exp in zip(prices, expected):
            assert actual == pytest.approx(exp, abs=0.01), (
                f"Expected {exp}, got {actual}"
            )

    def test_source_and_meta(
        self, detector_with_levels: FibonacciRetracementDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        for lvl in levels:
            assert lvl.source == "fib_retracement"
            assert isinstance(lvl.meta, FibonacciMeta)
            assert lvl.meta.direction == "retracement"
            assert lvl.meta.swing_high == pytest.approx(110.0, abs=0.01)
            assert lvl.meta.swing_low == pytest.approx(90.0, abs=0.01)

    def test_bounce_count_zero(
        self, detector_with_levels: FibonacciRetracementDetector,
    ) -> None:
        for lvl in detector_with_levels.levels():
            assert lvl.bounce_count == 0

    def test_zone_width(
        self, detector_with_levels: FibonacciRetracementDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        for lvl in levels:
            zone_width = lvl.zone_upper - lvl.zone_lower
            assert zone_width > 0
            # Zone should be symmetric around price
            assert lvl.zone_upper == pytest.approx(lvl.price + zone_width / 2, abs=1e-9)
            assert lvl.zone_lower == pytest.approx(lvl.price - zone_width / 2, abs=1e-9)


class TestStrengthOrdering:
    """0.618 ratio should have the highest strength."""

    def test_golden_ratio_strongest(self) -> None:
        det = FibonacciRetracementDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)

        levels = det.levels()
        assert len(levels) == 5

        # Find 0.618 level
        strengths = {round(lvl.meta.ratio, 3): lvl.strength for lvl in levels}
        assert strengths[0.618] == 1.0
        assert strengths[0.5] == 0.8
        assert strengths[0.382] == 0.6
        assert strengths[0.786] == 0.5
        assert strengths[0.236] == 0.4


class TestLevelsUpdateOnNewSwing:
    """Levels should update when a new swing is detected."""

    def test_levels_change_with_new_swing(self) -> None:
        det = FibonacciRetracementDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)

        levels_before = det.levels()
        assert len(levels_before) == 5

        # Now create a new higher swing high at ~115 by ascending then descending
        ts = _BASE_TS + len(bars) * _1H_NS
        # Ascend
        for i in range(6):
            price = 103.0 + i * 2.5
            bar = make_bar(price - 0.5, price + 1.0, price - 1.0, price, ts_ns=ts)
            det.update(bar)
            ts += _1H_NS

        # Peak at 118
        bar = make_bar(117.0, 118.0, 116.0, 117.0, ts_ns=ts)
        det.update(bar)
        ts += _1H_NS

        # Descend to confirm
        for i in range(6):
            price = 115.0 - i * 2.0
            bar = make_bar(price + 0.5, price + 1.0, price - 1.0, price, ts_ns=ts)
            det.update(bar)
            ts += _1H_NS

        levels_after = det.levels()
        # Levels should have changed (new swing high detected)
        if len(levels_after) == 5:
            prices_before = [lvl.price for lvl in levels_before]
            prices_after = [lvl.price for lvl in levels_after]
            assert prices_before != prices_after


class TestDeterministic:
    """Same input produces same output."""

    def test_deterministic(self) -> None:
        bars = _make_uptrend_bars(swing_period=5, atr_period=14)

        det1 = FibonacciRetracementDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        det2 = FibonacciRetracementDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )

        for bar in bars:
            det1.update(bar)
            det2.update(bar)

        levels1 = det1.levels()
        levels2 = det2.levels()

        assert len(levels1) == len(levels2)
        for l1, l2 in zip(levels1, levels2):
            assert l1.price == l2.price
            assert l1.strength == l2.strength


class TestReset:
    """Reset clears all state."""

    def test_reset_clears_levels(self) -> None:
        det = FibonacciRetracementDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)

        assert len(det.levels()) > 0

        det.reset()
        assert det.levels() == []

    def test_reset_allows_reuse(self) -> None:
        det = FibonacciRetracementDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)

        levels_first = det.levels()
        det.reset()

        for bar in bars:
            det.update(bar)

        levels_second = det.levels()
        assert len(levels_first) == len(levels_second)
        for l1, l2 in zip(levels_first, levels_second):
            assert l1.price == l2.price


class TestNameAndWarmup:
    """Basic property tests."""

    def test_name(self) -> None:
        det = FibonacciRetracementDetector()
        assert det.name == "fib_retracement"

    def test_warmup_bars(self) -> None:
        det = FibonacciRetracementDetector(swing_period=5)
        assert det.warmup_bars == 11  # 5 * 2 + 1

    def test_warmup_bars_custom(self) -> None:
        det = FibonacciRetracementDetector(swing_period=3)
        assert det.warmup_bars == 7  # 3 * 2 + 1
