"""Tests for FibonacciExtensionDetector."""

from __future__ import annotations

import pytest

from indicators.key_levels.detectors.fibonacci import FibonacciExtensionDetector
from indicators.key_levels.model import FibonacciMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_abc_uptrend_bars(
    swing_period: int = 5,
    atr_period: int = 14,
) -> list:
    """Build bars that produce 3 swings: low(90) -> high(110) -> low(95).

    This forms an A-B-C uptrend pattern for extension projection.
    A=90 (swing low), B=110 (swing high), C=95 (pullback low).
    Range = B - A = 20.
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

    # Phase 2: Descend to create swing low A at 90
    for i in range(swing_period):
        price = 98.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    # The swing low bar — low of 90
    _add(91.0, 91.5, 90.0, 91.0)

    # Ascend away from swing low
    for i in range(swing_period):
        price = 93.0 + i * 2.0
        _add(price, price + 0.5, price - 1.0, price)

    # Phase 3: Ascend to create swing high B at 110
    for i in range(swing_period):
        price = 103.0 + i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    # The swing high bar — high of 110
    _add(109.0, 110.0, 108.5, 109.0)

    # Descend away from swing high
    for i in range(swing_period):
        price = 108.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    # Phase 4: Descend to create swing low C at 95
    # Lows must stay strictly above 95 so the fractal center is unique
    for i in range(swing_period):
        price = 101.0 - i * 1.0
        _add(price, price + 0.5, price - 0.5, price)  # lows: 100.5, 99.5, 98.5, 97.5, 96.5

    # The swing low bar — low of 95 (strictly lower than all neighbours)
    _add(96.0, 96.5, 95.0, 96.0)

    # Ascend away from swing low to confirm it (lows strictly above 95)
    for i in range(swing_period):
        price = 97.0 + i * 1.5
        _add(price, price + 0.5, price - 0.5, price)  # lows: 96.5, 98.0, 99.5, 101.0, 102.5

    return bars


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoLevelsBeforeThreeSwings:
    """No levels produced until at least 3 swings are detected."""

    def test_no_levels_initially(self) -> None:
        det = FibonacciExtensionDetector(swing_period=5, atr_period=14)
        for i in range(10):
            bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS)
            det.update(bar)

        assert det.levels() == []

    def test_no_levels_with_two_swings(self) -> None:
        """Even with 2 swings, no extensions should be produced."""
        det = FibonacciExtensionDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
        # Feed only up to the point where 2 swings exist (before 3rd swing confirmed)
        # ATR(14) + descend(5) + low(1) + ascend(5) + approach(5) + high(1) = 31
        # After high is confirmed at bar 31 + swing_period = 36, we have 2 swings
        # Feed up to just before the 3rd swing confirmation
        partial_count = 14 + 5 + 1 + 5 + 5 + 1 + 5 + 5  # before 3rd low confirmed
        for bar in bars[:partial_count]:
            det.update(bar)

        assert det.levels() == []


class TestExtensionLevelsUptrend:
    """Verify correct extension levels for A=90(low), B=110(high), C=95(low)."""

    @pytest.fixture
    def detector_with_levels(self) -> FibonacciExtensionDetector:
        det = FibonacciExtensionDetector(
            swing_period=5,
            min_swing_atr_multiple=0.5,
            atr_period=14,
        )
        bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)
        return det

    def test_five_levels_produced(
        self, detector_with_levels: FibonacciExtensionDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        assert len(levels) == 5

    def test_level_prices(
        self, detector_with_levels: FibonacciExtensionDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        prices = [lvl.price for lvl in levels]

        # A=90, B=110, C=95, range=20, uptrend
        # ext_price = C + ratio * (B - A) = 95 + ratio * 20
        expected = [
            95.0 + 1.0 * 20,      # 115.0
            95.0 + 1.272 * 20,     # 120.44
            95.0 + 1.618 * 20,     # 127.36
            95.0 + 2.0 * 20,       # 135.0
            95.0 + 2.618 * 20,     # 147.36
        ]

        for actual, exp in zip(prices, expected):
            assert actual == pytest.approx(exp, abs=0.01), (
                f"Expected {exp}, got {actual}"
            )

    def test_source_and_meta(
        self, detector_with_levels: FibonacciExtensionDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        for lvl in levels:
            assert lvl.source == "fib_extension"
            assert isinstance(lvl.meta, FibonacciMeta)
            assert lvl.meta.direction == "extension"
            assert lvl.meta.swing_high == pytest.approx(110.0, abs=0.01)
            assert lvl.meta.swing_low == pytest.approx(90.0, abs=0.01)

    def test_bounce_count_zero(
        self, detector_with_levels: FibonacciExtensionDetector,
    ) -> None:
        for lvl in detector_with_levels.levels():
            assert lvl.bounce_count == 0

    def test_zone_width(
        self, detector_with_levels: FibonacciExtensionDetector,
    ) -> None:
        levels = detector_with_levels.levels()
        for lvl in levels:
            zone_width = lvl.zone_upper - lvl.zone_lower
            assert zone_width > 0
            assert lvl.zone_upper == pytest.approx(lvl.price + zone_width / 2, abs=1e-9)
            assert lvl.zone_lower == pytest.approx(lvl.price - zone_width / 2, abs=1e-9)


class TestStrengthOrdering:
    """1.618 ratio should have the highest strength."""

    def test_golden_ratio_strongest(self) -> None:
        det = FibonacciExtensionDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)

        levels = det.levels()
        assert len(levels) == 5

        strengths = {round(lvl.meta.ratio, 3): lvl.strength for lvl in levels}
        assert strengths[1.618] == 1.0
        assert strengths[1.0] == 0.8
        assert strengths[1.272] == 0.7
        assert strengths[2.0] == 0.6
        assert strengths[2.618] == 0.5


class TestDeterministic:
    """Same input produces same output."""

    def test_deterministic(self) -> None:
        bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)

        det1 = FibonacciExtensionDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        det2 = FibonacciExtensionDetector(
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
        det = FibonacciExtensionDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
        for bar in bars:
            det.update(bar)

        assert len(det.levels()) > 0

        det.reset()
        assert det.levels() == []

    def test_reset_allows_reuse(self) -> None:
        det = FibonacciExtensionDetector(
            swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
        )
        bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
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
        det = FibonacciExtensionDetector()
        assert det.name == "fib_extension"

    def test_warmup_bars(self) -> None:
        det = FibonacciExtensionDetector(swing_period=5)
        assert det.warmup_bars == 11  # 5 * 2 + 1

    def test_warmup_bars_custom(self) -> None:
        det = FibonacciExtensionDetector(swing_period=3)
        assert det.warmup_bars == 7  # 3 * 2 + 1
