from enum import Enum


GRADIENT_THRESHOLD = 0.02
FAST_LOOKBACK = 5
NORMAL_LOOKBACK = 5
SLOW_LOOKBACK = 5


class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


def calculate_gradients(data: list[float]) -> list[float]:
    if len(data) < 2:
        return []
    gradients: list[float] = []
    for i in range(1, len(data)):
        dy = data[i] - data[i - 1]
        dx = 2.0  # 2 bars equivalent, matching Rust implementation
        gradients.append(dy / dx)
    return gradients


def _gradient_to_direction(gradient: float, threshold: float) -> TrendDirection:
    if gradient > threshold:
        return TrendDirection.UP
    elif gradient < -threshold:
        return TrendDirection.DOWN
    return TrendDirection.FLAT


def get_trend_direction(
    gradients: list[float],
    bar: int,
    lookback: int,
    threshold: float = GRADIENT_THRESHOLD,
) -> TrendDirection:
    if bar < lookback:
        return TrendDirection.FLAT

    current_direction = _gradient_to_direction(gradients[bar], threshold)
    if current_direction == TrendDirection.FLAT:
        return TrendDirection.FLAT

    for i in range(bar - lookback, bar):
        if _gradient_to_direction(gradients[i], threshold) != current_direction:
            return TrendDirection.FLAT

    return current_direction
