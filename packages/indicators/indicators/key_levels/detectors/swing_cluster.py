"""SwingClusterDetector — placeholder for swing cluster detection.

This module is a stub to satisfy the package __init__.py import.
Full implementation is in a separate phase.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel


class SwingClusterDetector:
    """Placeholder swing cluster detector."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self._levels: list[KeyLevel] = []

    @property
    def name(self) -> str:
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return 1

    def update(self, bar: Bar) -> None:
        pass

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._levels = []
