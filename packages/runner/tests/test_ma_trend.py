from runner.strategies.ma_trend import (
    TrendDirection,
    calculate_gradients,
    get_trend_direction,
)

THRESHOLD = 0.02


def test_calculate_gradients_basic():
    data = [100.0, 101.0, 102.0, 103.0]
    gradients = calculate_gradients(data)
    assert len(gradients) == 3
    assert all(g == 0.5 for g in gradients)


def test_calculate_gradients_empty():
    assert calculate_gradients([]) == []
    assert calculate_gradients([100.0]) == []


def test_trend_direction_up_when_consecutive_positive():
    gradients = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    result = get_trend_direction(gradients, bar=6, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.UP


def test_trend_direction_down_when_consecutive_negative():
    gradients = [-0.5, -0.5, -0.5, -0.5, -0.5, -0.5, -0.5]
    result = get_trend_direction(gradients, bar=6, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.DOWN


def test_trend_direction_flat_when_mixed():
    gradients = [0.5, -0.5, 0.5, -0.5, 0.5, 0.5, 0.5]
    result = get_trend_direction(gradients, bar=6, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.FLAT


def test_trend_direction_flat_when_insufficient_bars():
    gradients = [0.5, 0.5]
    result = get_trend_direction(gradients, bar=1, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.FLAT


def test_trend_direction_flat_within_threshold():
    gradients = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01]
    result = get_trend_direction(gradients, bar=5, lookback=5, threshold=THRESHOLD)
    assert result == TrendDirection.FLAT
