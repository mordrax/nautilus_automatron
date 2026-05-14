import pytest

from indicators.spike.model import MoveMethod
from indicators.spike.moves import compute_move


# A 5-bar window. prior_close = closes[-N-1] = closes[0].
# closes/highs/lows lists have length N+1 (the bar at -N-1 plus N measurement bars).
WINDOW_UP = {
    "closes": [100.0, 101.0, 105.0, 110.0, 108.0, 107.0],
    "highs":  [100.5, 101.5, 105.5, 112.0, 109.0, 107.5],
    "lows":   [ 99.5, 100.5, 104.5, 109.5, 107.5, 106.5],
}
WINDOW_ROUND_TRIP = {
    # net move is small (+1) but intra-window high spiked to 112
    "closes": [100.0, 102.0, 112.0, 105.0, 102.0, 101.0],
    "highs":  [100.5, 102.5, 112.5, 105.5, 102.5, 101.5],
    "lows":   [ 99.5, 101.5, 104.0, 104.5, 101.5, 100.5],
}


def test_net_directional_close_to_close():
    m = compute_move(MoveMethod.NET, **WINDOW_UP)
    assert m.direction == 1
    assert m.magnitude == pytest.approx(7.0)  # 107 - 100


def test_excursion_captures_round_trip():
    m = compute_move(MoveMethod.EXCURSION, **WINDOW_ROUND_TRIP)
    # up_excursion = max(highs[-5:]) - prior_close = 112.5 - 100 = 12.5
    # down_excursion = 100 - min(lows[-5:]) = 100 - 100.5 = -0.5 (clipped to 0)
    assert m.direction == 1
    assert m.magnitude == pytest.approx(12.5)


def test_range_uses_high_low_signed_by_net():
    m = compute_move(MoveMethod.RANGE, **WINDOW_ROUND_TRIP)
    # range = 112.5 - 100.5 = 12.0; net = 101 - 100 = +1 → direction +1
    assert m.direction == 1
    assert m.magnitude == pytest.approx(12.0)


def test_range_direction_negative_when_net_down():
    closes = [100.0, 99.0, 95.0, 90.0, 92.0, 94.0]
    highs  = [100.5, 99.5, 95.5, 91.0, 93.0, 94.5]
    lows   = [ 99.5, 94.0, 89.5, 89.0, 91.0, 93.5]
    m = compute_move(MoveMethod.RANGE, closes=closes, highs=highs, lows=lows)
    # max(highs[1:]) = max(99.5, 95.5, 91.0, 93.0, 94.5) = 99.5
    # min(lows[1:])  = min(94.0, 89.5, 89.0, 91.0, 93.5) = 89.0
    # range = 99.5 - 89.0 = 10.5; net = 94 - 100 = -6 → direction -1
    assert m.direction == -1
    assert m.magnitude == pytest.approx(10.5)
