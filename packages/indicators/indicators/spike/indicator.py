"""SpikeIndicator — directional price-spike detector with optional volume confirmation.

Detects when the recent N-bar |move| is abnormally large vs the baseline
distribution of N-bar moves over the preceding M bars, optionally confirmed
by abnormal volume. See docs/specs/spike-indicator.md.
"""

from __future__ import annotations

from collections import deque
from statistics import mean, median, pstdev
from typing import Deque, List

from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.indicators.base import Indicator
from nautilus_trader.model.data import Bar

from indicators.spike.model import (
    MoveMethod,
    Spike,
    Statistic,
    VolumeMode,
)
from indicators.spike.moves import MoveResult, compute_move

_INPUT_VOLUME_MODES: frozenset[VolumeMode] = frozenset(
    {VolumeMode.AUTO, VolumeMode.ALWAYS, VolumeMode.NEVER}
)


class SpikeIndicator(Indicator):
    def __init__(
        self,
        move_method: MoveMethod = MoveMethod.EXCURSION,
        statistic: Statistic = Statistic.ZSCORE,
        measurement_window: int = 5,
        baseline_window: int = 20,
        price_threshold: float = 2.5,
        volume_threshold: float = 2.0,
        cooldown_bars: int = 20,
        require_volume: VolumeMode = VolumeMode.AUTO,
        max_spikes: int = 10000,
    ) -> None:
        if not isinstance(move_method, MoveMethod):
            raise ValueError(f"move_method must be MoveMethod, got {move_method!r}")
        if not isinstance(statistic, Statistic):
            raise ValueError(f"statistic must be Statistic, got {statistic!r}")
        if require_volume not in _INPUT_VOLUME_MODES:
            raise ValueError(
                f"require_volume must be AUTO/ALWAYS/NEVER, got {require_volume!r}"
            )

        PyCondition.positive_int(measurement_window, "measurement_window")
        PyCondition.positive_int(baseline_window, "baseline_window")
        if baseline_window <= measurement_window:
            raise ValueError("baseline_window must be > measurement_window")
        if price_threshold < 0:
            raise ValueError("price_threshold must be >= 0")
        if volume_threshold < 0:
            raise ValueError("volume_threshold must be >= 0")
        if cooldown_bars < 0:
            raise ValueError("cooldown_bars must be >= 0")
        PyCondition.not_negative_int(max_spikes, "max_spikes")

        super().__init__(
            params=[
                move_method.value,
                statistic.value,
                measurement_window,
                baseline_window,
                price_threshold,
                volume_threshold,
                cooldown_bars,
                require_volume.value,
                max_spikes,
            ]
        )

        self.move_method = move_method
        self.statistic = statistic
        self.measurement_window = measurement_window
        self.baseline_window = baseline_window
        self.price_threshold = price_threshold
        self.volume_threshold = volume_threshold
        self.cooldown_bars = cooldown_bars
        self.require_volume = require_volume
        self.max_spikes = max_spikes

        buf_size = baseline_window + measurement_window + 1
        self._closes: Deque[float] = deque(maxlen=buf_size)
        self._highs: Deque[float] = deque(maxlen=buf_size)
        self._lows: Deque[float] = deque(maxlen=buf_size)
        self._volumes: Deque[float] = deque(maxlen=buf_size)
        self._timestamps: Deque[int] = deque(maxlen=buf_size)

        self._spikes: Deque[Spike] | List[Spike] = (
            deque(maxlen=max_spikes) if max_spikes > 0 else []
        )

        self.volume_mode: VolumeMode | None = None
        self.direction: int = 0
        self.changed: bool = False
        self.current_spike: Spike | None = None
        self.spike_count: int = 0

        self._bar_index: int = 0
        self._cooldown_remaining: int = 0

    @property
    def spikes(self) -> list[Spike]:
        return list(self._spikes)

    def _reset(self) -> None:
        self._closes.clear()
        self._highs.clear()
        self._lows.clear()
        self._volumes.clear()
        self._timestamps.clear()
        if isinstance(self._spikes, deque):
            self._spikes.clear()
        else:
            self._spikes = []
        self.volume_mode = None
        self.direction = 0
        self.changed = False
        self.current_spike = None
        self.spike_count = 0
        self._bar_index = 0
        self._cooldown_remaining = 0
