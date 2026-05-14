"""Three pure move-calculation strategies for SpikeIndicator.

Each function takes the last N+1 closes/highs/lows (where N = measurement_window)
and returns a (magnitude, direction) pair. magnitude is always non-negative;
direction is +1 / -1 / 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from indicators.spike.model import MoveMethod


@dataclass(frozen=True)
class MoveResult:
    magnitude: float
    # +1 / -1 / 0. For NET, direction == 0 iff magnitude == 0. For RANGE the
    # direction is signed by net close-to-close, so direction can be 0 even
    # when magnitude > 0 (flat-close round-trip window). Callers must guard.
    direction: int


def compute_move(
    method: MoveMethod,
    *,
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
) -> MoveResult:
    """Compute the recent N-bar move for the given method.

    closes/highs/lows must each have length >= 2. The last element is the
    firing bar; closes[0] / highs[0] / lows[0] is the bar at index -N-1.
    The measurement window is the last N = len(closes) - 1 bars.
    """
    if not (len(closes) == len(highs) == len(lows)) or len(closes) < 2:
        raise ValueError("closes, highs, lows must be same length >= 2")

    prior_close = closes[0]
    last_close = closes[-1]

    if method is MoveMethod.NET:
        move = last_close - prior_close
        return MoveResult(magnitude=abs(move), direction=_sign(move))

    win_highs = highs[1:]
    win_lows = lows[1:]

    if method is MoveMethod.EXCURSION:
        up = max(win_highs) - prior_close
        down = prior_close - min(win_lows)
        if up >= down:
            return MoveResult(magnitude=max(up, 0.0), direction=1)
        return MoveResult(magnitude=max(down, 0.0), direction=-1)

    if method is MoveMethod.RANGE:
        rng = max(win_highs) - min(win_lows)
        net = last_close - prior_close
        return MoveResult(magnitude=rng, direction=_sign(net))

    raise ValueError(f"Unknown MoveMethod: {method!r}")


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
