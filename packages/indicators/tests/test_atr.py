"""Tests for streaming ATR helper."""

import pytest

from indicators.key_levels.shared.atr import StreamingAtr


def test_atr_not_ready_before_warmup():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)
    assert not atr.ready
    assert atr.value == 0.0


def test_atr_ready_after_warmup():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)   # TR=10
    atr.update(high=110.0, low=98.0, close=105.0)    # TR=12
    atr.update(high=108.0, low=100.0, close=103.0)   # TR=8
    assert atr.ready
    assert atr.value == pytest.approx(10.0, abs=0.01)  # SMA of [10, 12, 8]


def test_atr_wilder_smoothing_after_warmup():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)    # TR=10
    atr.update(high=110.0, low=98.0, close=105.0)    # TR=12
    atr.update(high=108.0, low=100.0, close=103.0)   # TR=8, ATR=10.0
    atr.update(high=106.0, low=101.0, close=104.0)   # TR=5, ATR=(10*2+5)/3=8.333
    assert atr.value == pytest.approx(25.0 / 3.0, abs=0.01)


def test_atr_reset():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)
    atr.update(high=110.0, low=98.0, close=105.0)
    atr.update(high=108.0, low=100.0, close=103.0)
    assert atr.ready
    atr.reset()
    assert not atr.ready
    assert atr.value == 0.0


def test_atr_deterministic():
    bars = [
        (105.0, 95.0, 100.0),
        (110.0, 98.0, 105.0),
        (108.0, 100.0, 103.0),
        (106.0, 101.0, 104.0),
    ]
    atr_a = StreamingAtr(period=3)
    atr_b = StreamingAtr(period=3)
    for h, lo, c in bars:
        atr_a.update(h, lo, c)
        atr_b.update(h, lo, c)
    assert atr_a.value == atr_b.value
