"""SpikeIndicator — directional price-spike detector with optional volume confirmation.

Detects when the recent N-bar |move| is abnormally large vs the baseline
distribution of N-bar moves over the preceding M bars, optionally confirmed
by abnormal volume. See docs/specs/spike-indicator.md.
"""

from __future__ import annotations

from collections import deque
from statistics import mean, median, pstdev

from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.indicators.base import Indicator
from nautilus_trader.model.data import Bar

from indicators.spike.model import (
    MoveMethod,
    Spike,
    Statistic,
    VolumeMode,
)
from indicators.spike.moves import compute_move

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
        self._closes: deque[float] = deque(maxlen=buf_size)
        self._highs: deque[float] = deque(maxlen=buf_size)
        self._lows: deque[float] = deque(maxlen=buf_size)
        self._volumes: deque[float] = deque(maxlen=buf_size)
        self._timestamps: deque[int] = deque(maxlen=buf_size)

        self._spikes: deque[Spike] | list[Spike] = (
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
        self._set_has_inputs(False)
        self._set_initialized(False)

    def handle_bar(self, bar: Bar) -> None:
        PyCondition.not_none(bar, "bar")
        self._update(
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=float(bar.volume),
            ts_ns=bar.ts_init,
        )

    def _update(
        self,
        high: float,
        low: float,
        close: float,
        volume: float,
        ts_ns: int,
    ) -> None:
        self._closes.append(close)
        self._highs.append(high)
        self._lows.append(low)
        self._volumes.append(volume)
        self._timestamps.append(ts_ns)
        self._bar_index += 1

        if not self.has_inputs:
            self._set_has_inputs(True)

        self.changed = False

        if len(self._closes) < self._closes.maxlen:
            return  # still warming up

        if self.volume_mode is None:
            self.volume_mode = self._latch_volume_mode()
            self._set_initialized(True)

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return

        N = self.measurement_window
        closes_win = list(self._closes)[-(N + 1):]
        highs_win = list(self._highs)[-(N + 1):]
        lows_win = list(self._lows)[-(N + 1):]
        result = compute_move(
            self.move_method,
            closes=closes_win,
            highs=highs_win,
            lows=lows_win,
        )

        if result.direction == 0 or result.magnitude <= 0.0:
            return

        baseline_moves = self._baseline_moves_excluding_current()
        if len(baseline_moves) < 2:
            return

        if not self._price_rule_passes(result.magnitude, baseline_moves):
            return

        if self.volume_mode is VolumeMode.PRICE_AND_VOLUME:
            recent_vol = sum(list(self._volumes)[-N:])
            baseline_vols = self._baseline_volumes_excluding_current()
            if len(baseline_vols) < 2:
                return
            if not self._volume_rule_passes(recent_vol, baseline_vols):
                return
            volume_ratio: float | None = recent_vol / max(
                _baseline_centre(self.statistic, baseline_vols), 1e-12
            )
        else:
            volume_ratio = None

        spike = Spike(
            direction=result.direction,
            magnitude=result.magnitude,
            price_at_fire=close,
            start_ts=list(self._timestamps)[-(N + 1)],
            end_ts=ts_ns,
            start_bar_index=self._bar_index - N - 1,
            end_bar_index=self._bar_index - 1,
            volume_ratio=volume_ratio,
            move_method=self.move_method,
            statistic=self.statistic,
        )
        self._spikes.append(spike)
        self.current_spike = spike
        self.spike_count += 1
        self.direction = result.direction
        self.changed = True
        self._cooldown_remaining = self.cooldown_bars

    def _latch_volume_mode(self) -> VolumeMode:
        if self.require_volume is VolumeMode.ALWAYS:
            return VolumeMode.PRICE_AND_VOLUME
        if self.require_volume is VolumeMode.NEVER:
            return VolumeMode.PRICE_ONLY
        # AUTO
        vols = list(self._volumes)
        non_zero = any(v != 0 for v in vols)
        not_all_identical = len(set(vols)) > 1
        if non_zero and not_all_identical:
            return VolumeMode.PRICE_AND_VOLUME
        return VolumeMode.PRICE_ONLY

    def _baseline_moves_excluding_current(self) -> list[float]:
        """Compute |move| for every overlapping N-bar window inside the preceding
        baseline_window bars (i.e. excluding the current measurement window)."""
        N = self.measurement_window
        M = self.baseline_window
        closes = list(self._closes)
        highs = list(self._highs)
        lows = list(self._lows)
        out: list[float] = []
        for k in range(0, M - N + 1):
            sub_closes = closes[k : k + N + 1]
            sub_highs = highs[k : k + N + 1]
            sub_lows = lows[k : k + N + 1]
            r = compute_move(
                self.move_method,
                closes=sub_closes,
                highs=sub_highs,
                lows=sub_lows,
            )
            out.append(r.magnitude)
        return out

    def _baseline_volumes_excluding_current(self) -> list[float]:
        """Cumulative N-bar volumes over the same M-N+1 overlapping windows used
        by `_baseline_moves_excluding_current`, time-aligned with the price
        baseline (each baseline window's measurement bars are vols[k+1 : k+N+1])."""
        N = self.measurement_window
        M = self.baseline_window
        vols = list(self._volumes)
        out: list[float] = []
        for k in range(0, M - N + 1):
            out.append(sum(vols[k + 1 : k + N + 1]))
        return out

    def _price_rule_passes(self, magnitude: float, baseline: list[float]) -> bool:
        return _statistic_rule_passes(
            self.statistic, magnitude, baseline, self.price_threshold
        )

    def _volume_rule_passes(self, recent: float, baseline: list[float]) -> bool:
        return _statistic_rule_passes(
            self.statistic, recent, baseline, self.volume_threshold
        )


def _baseline_centre(statistic: Statistic, samples: list[float]) -> float:
    if statistic is Statistic.MEDIAN:
        return median(samples)
    return mean(samples)


def _statistic_rule_passes(
    statistic: Statistic,
    recent: float,
    baseline: list[float],
    threshold: float,
) -> bool:
    if statistic is Statistic.MEAN:
        return recent >= mean(baseline) * threshold
    if statistic is Statistic.MEDIAN:
        return recent >= median(baseline) * threshold
    if statistic is Statistic.ZSCORE:
        mu = mean(baseline)
        sigma = pstdev(baseline) if len(baseline) > 1 else 0.0
        if sigma == 0.0:
            return False
        return (recent - mu) / sigma >= threshold
    raise ValueError(f"Unknown statistic: {statistic!r}")
