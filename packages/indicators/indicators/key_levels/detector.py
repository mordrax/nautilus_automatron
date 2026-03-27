"""KeyLevelDetector protocol — the contract all detection methods implement."""

from __future__ import annotations

from typing import Protocol

from nautilus_trader.model.data import Bar

from indicators.key_levels.model import KeyLevel, Source


class KeyLevelDetector(Protocol):
    @property
    def name(self) -> Source: ...

    @property
    def warmup_bars(self) -> int:
        """Minimum bars needed before this detector can produce levels."""
        ...

    def update(self, bar: Bar) -> None:
        """Ingest a new bar and update internal state."""
        ...

    def levels(self) -> list[KeyLevel]:
        """Return all currently active levels."""
        ...

    def reset(self) -> None:
        """Reset all internal state."""
        ...
