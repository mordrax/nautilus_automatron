"""Tests for bar factory utility."""

import pytest

from tests.helpers.bar_factory import (
    make_bar,
    make_bars_from_closes,
    make_bars_from_ohlcv,
)


def test_make_bar_returns_correct_ohlcv():
    bar = make_bar(100.0, 105.0, 95.0, 102.0, 500.0)
    assert float(bar.open) == pytest.approx(100.0, abs=1e-4)
    assert float(bar.high) == pytest.approx(105.0, abs=1e-4)
    assert float(bar.low) == pytest.approx(95.0, abs=1e-4)
    assert float(bar.close) == pytest.approx(102.0, abs=1e-4)
    assert float(bar.volume) == pytest.approx(500.0, abs=1e-1)


def test_make_bar_timestamps():
    bar1 = make_bar(1.0, 2.0, 0.5, 1.5, ts_ns=1000)
    assert bar1.ts_event == 1000
    assert bar1.ts_init == 1000


def test_make_bars_from_ohlcv_count_and_timestamps():
    data = [
        (100.0, 105.0, 95.0, 102.0, 100.0),
        (102.0, 108.0, 100.0, 106.0, 200.0),
        (106.0, 107.0, 103.0, 104.0, 150.0),
    ]
    bars = make_bars_from_ohlcv(data, start_ts=0, interval_ns=1000)
    assert len(bars) == 3
    assert bars[0].ts_event == 0
    assert bars[1].ts_event == 1000
    assert bars[2].ts_event == 2000
    assert float(bars[1].close) == pytest.approx(106.0, abs=1e-4)


def test_make_bars_from_closes_generates_valid_bars():
    closes = [100.0, 102.0, 98.0, 103.0]
    bars = make_bars_from_closes(closes, spread=1.0)
    assert len(bars) == 4
    for bar in bars:
        assert float(bar.high) >= float(bar.low)
        assert float(bar.high) >= float(bar.close)
        assert float(bar.low) <= float(bar.close)
