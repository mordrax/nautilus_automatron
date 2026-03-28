"""ZigZag pivot data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZigZagPivot:
    """A confirmed zigzag pivot point.

    Parameters
    ----------
    price : float
        The pivot price (high or low).
    timestamp : int
        Nanosecond timestamp (bar.ts_init) when the pivot was set.
    direction : int
        1 = swing high, -1 = swing low.
    bar_index : int
        Bar count when pivot was confirmed.
    """

    price: float
    timestamp: int
    direction: int
    bar_index: int
