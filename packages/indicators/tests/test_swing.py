"""Tests for SwingDetector (Williams fractal detection)."""

import pytest

from indicators.key_levels.shared.swing import Swing, SwingDetector


def test_swing_detector_no_swings_before_warmup():
    sd = SwingDetector(period=2)
    sd.update(high=100.0, low=90.0, bar_index=0, ts=0)
    sd.update(high=105.0, low=95.0, bar_index=1, ts=1000)
    assert sd.swings() == []


def test_swing_detector_finds_fractal_high():
    """A fractal high with period=2 requires bar[i].high > all 4 surrounding bars."""
    sd = SwingDetector(period=2)
    highs = [100.0, 105.0, 110.0, 105.0, 100.0]
    lows = [95.0, 100.0, 105.0, 100.0, 95.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)

    swings = sd.swings()
    swing_highs = [s for s in swings if s.side == "high"]
    assert len(swing_highs) == 1
    assert swing_highs[0].price == 110.0
    assert swing_highs[0].bar_index == 2


def test_swing_detector_finds_fractal_low():
    sd = SwingDetector(period=2)
    highs = [110.0, 105.0, 100.0, 105.0, 110.0]
    lows = [100.0, 95.0, 90.0, 95.0, 100.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)

    swings = sd.swings()
    swing_lows = [s for s in swings if s.side == "low"]
    assert len(swing_lows) == 1
    assert swing_lows[0].price == 90.0
    assert swing_lows[0].bar_index == 2


def test_swing_detector_period_3():
    sd = SwingDetector(period=3)
    highs = [100.0, 103.0, 106.0, 110.0, 106.0, 103.0, 100.0]
    lows = [95.0, 98.0, 101.0, 105.0, 101.0, 98.0, 95.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)

    swing_highs = [s for s in sd.swings() if s.side == "high"]
    assert len(swing_highs) == 1
    assert swing_highs[0].bar_index == 3


def test_swing_detector_multiple_swings():
    sd = SwingDetector(period=2)
    highs = [100, 105, 110, 105, 100, 105, 110, 105, 100]
    lows = [95, 100, 105, 100, 95, 100, 105, 100, 95]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=float(h), low=float(l), bar_index=i, ts=i * 1000)

    swings = sd.swings()
    assert len(swings) >= 2


def test_swing_detector_reset():
    sd = SwingDetector(period=2)
    highs = [100.0, 105.0, 110.0, 105.0, 100.0]
    lows = [95.0, 100.0, 105.0, 100.0, 95.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)
    assert len(sd.swings()) > 0
    sd.reset()
    assert sd.swings() == []


def test_swing_detector_deterministic():
    highs = [100.0, 105.0, 110.0, 105.0, 100.0, 95.0, 100.0]
    lows = [95.0, 100.0, 105.0, 100.0, 95.0, 90.0, 95.0]
    sd_a = SwingDetector(period=2)
    sd_b = SwingDetector(period=2)
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd_a.update(high=h, low=l, bar_index=i, ts=i * 1000)
        sd_b.update(high=h, low=l, bar_index=i, ts=i * 1000)
    assert sd_a.swings() == sd_b.swings()
