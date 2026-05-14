# Spike Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single `SpikeIndicator` (with `NET` / `EXCURSION` / `RANGE` move methods and `MEAN` / `MEDIAN` / `ZSCORE` statistics) end-to-end — math, tests, backend registration, frontend wiring — with the framework extended to support enum parameters.

**Architecture:** Add `"enum"` to the existing `ParamSchema` framework. Implement `SpikeIndicator` as a Nautilus `Indicator` subclass with three pure move-calculation helpers, rolling buffers, baseline statistics, and cooldown. Register under `"Spike"` in `INDICATOR_TYPES` with all 9 params exposed. Frontend renders firing bars via existing eCharts primitives.

**Tech Stack:** Python 3.12, `nautilus_trader.indicators.base.Indicator`, `pytest`, frozen dataclasses, `Enum`, statistics from `math`/`statistics`. Frontend: React + Vite + Effect-TS + shadcn `<Select>` + eCharts scatter.

---

## File Plan

**Create:**
- `packages/indicators/indicators/spike/__init__.py`
- `packages/indicators/indicators/spike/model.py`
- `packages/indicators/indicators/spike/moves.py`
- `packages/indicators/indicators/spike/indicator.py`
- `packages/indicators/tests/test_spike_moves.py`
- `packages/indicators/tests/test_spike_indicator.py`

**Modify:**
- `packages/server/server/store/indicators.py` (extend `ParamSchema` with `"enum"`; register `"Spike"`; add `_compute_spike`)
- `packages/server/tests/test_indicators_store.py` (add Spike + enum-param tests — adjust path if it lives elsewhere)
- `packages/client/src/types/api.ts` (`ParamSchema.type` gains `"enum"` + `choices`)
- `packages/client/src/lib/indicator-params.ts` (coerce + validate enum)
- `packages/client/src/lib/indicator-params.test.ts` (enum cases)
- `packages/client/src/components/chart/indicator-selector/IndicatorParamForm.tsx` (render `<Select>` for enum)
- `packages/client/src/components/chart/indicator-selector/IndicatorParamForm.test.tsx` (enum-field tests)
- `packages/client/src/components/chart/CandlestickChart.tsx` (render Spike series)
- `packages/client/e2e/spike-indicator.spec.ts` (new Playwright test — created in Task 11)

Each task is independently committable.

---

## Task 1: Spike data model — enums and `Spike` dataclass

**Files:**
- Create: `packages/indicators/indicators/spike/model.py`
- Create: `packages/indicators/indicators/spike/__init__.py`
- Test: `packages/indicators/tests/test_spike_indicator.py` (one model test seeds the file)

- [ ] **Step 1: Write the failing test**

`packages/indicators/tests/test_spike_indicator.py`:
```python
from indicators.spike.model import Spike, MoveMethod, Statistic, VolumeMode


def test_spike_dataclass_is_frozen_and_typed():
    s = Spike(
        direction=1,
        magnitude=2.5,
        price_at_fire=100.0,
        start_ts=1,
        end_ts=10,
        start_bar_index=0,
        end_bar_index=4,
        volume_ratio=1.7,
        move_method=MoveMethod.EXCURSION,
        statistic=Statistic.ZSCORE,
    )
    assert s.direction == 1
    assert s.volume_ratio == 1.7
    try:
        s.direction = -1  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Spike must be frozen")


def test_volume_mode_runtime_states():
    assert VolumeMode.PRICE_AND_VOLUME in VolumeMode
    assert VolumeMode.PRICE_ONLY in VolumeMode
    assert VolumeMode.AUTO in VolumeMode
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'indicators.spike'`.

- [ ] **Step 3: Implement**

`packages/indicators/indicators/spike/__init__.py`:
```python
from indicators.spike.indicator import SpikeIndicator
from indicators.spike.model import MoveMethod, Spike, Statistic, VolumeMode

__all__ = ["SpikeIndicator", "Spike", "MoveMethod", "Statistic", "VolumeMode"]
```

`packages/indicators/indicators/spike/model.py`:
```python
"""Spike indicator data model — enums and Spike frozen dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MoveMethod(str, Enum):
    NET = "NET"
    EXCURSION = "EXCURSION"
    RANGE = "RANGE"


class Statistic(str, Enum):
    MEAN = "MEAN"
    MEDIAN = "MEDIAN"
    ZSCORE = "ZSCORE"


class VolumeMode(str, Enum):
    AUTO = "AUTO"
    ALWAYS = "ALWAYS"
    NEVER = "NEVER"
    PRICE_AND_VOLUME = "PRICE_AND_VOLUME"
    PRICE_ONLY = "PRICE_ONLY"


@dataclass(frozen=True)
class Spike:
    direction: int
    magnitude: float
    price_at_fire: float
    start_ts: int
    end_ts: int
    start_bar_index: int
    end_bar_index: int
    volume_ratio: float | None
    move_method: MoveMethod
    statistic: Statistic
```

Note: `indicator.py` is created in Task 3. Step 4 runs only the model tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py::test_spike_dataclass_is_frozen_and_typed tests/test_spike_indicator.py::test_volume_mode_runtime_states -v`
Expected: 2 passed.

(The `__init__.py` imports `SpikeIndicator` which doesn't exist yet; importing the module path `indicators.spike.model` directly bypasses that. The tests in Step 1 import from `indicators.spike.model`, not `indicators.spike`, so this works. If `__init__.py` raises on import, switch to importing `model.py` only and add the re-export when `indicator.py` exists in Task 3.)

- [ ] **Step 5: Commit**

```bash
cd packages/indicators && uv run pytest tests/test_spike_indicator.py -v
cd /Users/mordrax/code/nautilus_automatron/.worktrees/spike-indicator
git add packages/indicators/indicators/spike/__init__.py \
        packages/indicators/indicators/spike/model.py \
        packages/indicators/tests/test_spike_indicator.py
git commit -m "feat(spike): add Spike dataclass and enums"
```

---

## Task 2: Move-calculation helpers — three pure functions

**Files:**
- Create: `packages/indicators/indicators/spike/moves.py`
- Test: `packages/indicators/tests/test_spike_moves.py`

- [ ] **Step 1: Write the failing tests**

`packages/indicators/tests/test_spike_moves.py`:
```python
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
    # down_excursion = 100 - min(lows[-5:]) = 100 - 100.5 = -0.5 (clipped to 0 conceptually)
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
    assert m.direction == -1
    assert m.magnitude == pytest.approx(highs[1:][2] - lows[1:][2])  # 95.5 - 89.5 = 6.0 — verify exact
```

(The last assertion's arithmetic: max of highs[-5:] = max(99.5, 95.5, 91.0, 93.0, 94.5) = 99.5; min of lows[-5:] = 89.0; range = 10.5. Replace the last assertion with `assert m.magnitude == pytest.approx(10.5)`.)

Replace the last assertion to:
```python
    assert m.magnitude == pytest.approx(10.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/indicators && uv run pytest tests/test_spike_moves.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'indicators.spike.moves'`.

- [ ] **Step 3: Implement**

`packages/indicators/indicators/spike/moves.py`:
```python
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
    direction: int  # +1 / -1; 0 only when magnitude == 0


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/indicators && uv run pytest tests/test_spike_moves.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron/.worktrees/spike-indicator
git add packages/indicators/indicators/spike/moves.py \
        packages/indicators/tests/test_spike_moves.py
git commit -m "feat(spike): add move-calculation helpers (NET/EXCURSION/RANGE)"
```

---

## Task 3: SpikeIndicator skeleton — construction + validation

**Files:**
- Create: `packages/indicators/indicators/spike/indicator.py`
- Test: `packages/indicators/tests/test_spike_indicator.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `packages/indicators/tests/test_spike_indicator.py`:
```python
import pytest

from indicators.spike import SpikeIndicator
from indicators.spike.model import MoveMethod, Statistic, VolumeMode


def test_constructs_with_defaults():
    ind = SpikeIndicator()
    assert ind.move_method is MoveMethod.EXCURSION
    assert ind.statistic is Statistic.ZSCORE
    assert ind.measurement_window == 5
    assert ind.baseline_window == 20
    assert ind.cooldown_bars == 20
    assert ind.has_inputs is False
    assert ind.initialized is False
    assert ind.spike_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"measurement_window": 0},
        {"measurement_window": -1},
        {"baseline_window": 5, "measurement_window": 5},  # M must be > N
        {"price_threshold": -0.1},
        {"volume_threshold": -1.0},
        {"cooldown_bars": -1},
        {"max_spikes": -1},
    ],
)
def test_parameter_validation_rejects_invalid(kwargs):
    with pytest.raises((ValueError, Exception)):
        SpikeIndicator(**kwargs)


def test_per_statistic_threshold_defaults_applied():
    z = SpikeIndicator(statistic=Statistic.ZSCORE)
    m = SpikeIndicator(statistic=Statistic.MEAN)
    assert z.price_threshold == 2.5
    assert m.price_threshold == 3.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py::test_constructs_with_defaults -v`
Expected: FAIL with `ImportError: cannot import name 'SpikeIndicator'`.

- [ ] **Step 3: Implement (construction + validation only — handle_bar comes in Task 4)**

`packages/indicators/indicators/spike/indicator.py`:
```python
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

_PRICE_THRESHOLD_DEFAULTS: dict[Statistic, float] = {
    Statistic.MEAN: 3.0,
    Statistic.MEDIAN: 3.0,
    Statistic.ZSCORE: 2.5,
}
_VOLUME_THRESHOLD_DEFAULTS: dict[Statistic, float] = {
    Statistic.MEAN: 2.0,
    Statistic.MEDIAN: 2.0,
    Statistic.ZSCORE: 2.0,
}

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
        price_threshold: float | None = None,
        volume_threshold: float | None = None,
        cooldown_bars: int | None = None,
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
        PyCondition.not_negative_int(max_spikes, "max_spikes")

        resolved_price_threshold = (
            price_threshold
            if price_threshold is not None
            else _PRICE_THRESHOLD_DEFAULTS[statistic]
        )
        resolved_volume_threshold = (
            volume_threshold
            if volume_threshold is not None
            else _VOLUME_THRESHOLD_DEFAULTS[statistic]
        )
        if resolved_price_threshold < 0:
            raise ValueError("price_threshold must be >= 0")
        if resolved_volume_threshold < 0:
            raise ValueError("volume_threshold must be >= 0")

        resolved_cooldown = cooldown_bars if cooldown_bars is not None else baseline_window
        if resolved_cooldown < 0:
            raise ValueError("cooldown_bars must be >= 0")

        super().__init__(
            params=[
                move_method.value,
                statistic.value,
                measurement_window,
                baseline_window,
                resolved_price_threshold,
                resolved_volume_threshold,
                resolved_cooldown,
                require_volume.value,
                max_spikes,
            ]
        )

        self.move_method = move_method
        self.statistic = statistic
        self.measurement_window = measurement_window
        self.baseline_window = baseline_window
        self.price_threshold = resolved_price_threshold
        self.volume_threshold = resolved_volume_threshold
        self.cooldown_bars = resolved_cooldown
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py -v`
Expected: all tests pass (model + construction + validation + defaults).

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/spike/indicator.py \
        packages/indicators/tests/test_spike_indicator.py
git commit -m "feat(spike): SpikeIndicator construction + parameter validation"
```

---

## Task 4: SpikeIndicator runtime — `handle_bar`, baseline, rules, cooldown, latching

**Files:**
- Modify: `packages/indicators/indicators/spike/indicator.py` (add methods)
- Test: `packages/indicators/tests/test_spike_indicator.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_spike_indicator.py`:
```python
from indicators.tests.helpers.bar_factory import make_bar  # adjust import path per repo convention


def _bars(closes, highs=None, lows=None, volumes=None, start_ns=1_000_000_000):
    highs = highs if highs is not None else [c + 0.5 for c in closes]
    lows  = lows  if lows  is not None else [c - 0.5 for c in closes]
    volumes = volumes if volumes is not None else [100.0] * len(closes)
    out = []
    for i, c in enumerate(closes):
        out.append(make_bar(
            open=c, high=highs[i], low=lows[i], close=c, volume=volumes[i],
            ts_init=start_ns + i * 60_000_000_000,
        ))
    return out


def test_no_spike_on_flat_series():
    ind = SpikeIndicator(measurement_window=3, baseline_window=10)
    for bar in _bars([100.0] * 30):
        ind.handle_bar(bar)
    assert ind.spike_count == 0
    assert ind.volume_mode is VolumeMode.PRICE_AND_VOLUME  # constant non-zero volume → latches volume mode... see latching rule
```

Note: per spec, "non-zero AND not all identical". Constant non-zero volume is NOT usable → latches `PRICE_ONLY`. Adjust assertion:
```python
    assert ind.volume_mode is VolumeMode.PRICE_ONLY
```

Continue with more tests:
```python
def test_up_spike_with_volume_fires():
    closes = [100.0] * 25 + [100.5, 101.0, 110.0]  # spike in last 3 bars
    volumes = [100.0] * 25 + [300.0, 350.0, 400.0]  # volume also abnormal
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=2.0,
        volume_threshold=2.0,
    )
    for bar in _bars(closes, volumes=volumes):
        ind.handle_bar(bar)
    assert ind.spike_count == 1
    assert ind.current_spike is not None
    assert ind.current_spike.direction == 1
    assert ind.volume_mode is VolumeMode.PRICE_AND_VOLUME


def test_price_passes_volume_blocks_no_fire():
    closes = [100.0] * 25 + [100.5, 101.0, 110.0]
    volumes = [100.0] * 28  # volume stays flat
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=2.0,
        volume_threshold=2.0,
        require_volume=VolumeMode.ALWAYS,
    )
    for bar in _bars(closes, volumes=volumes):
        ind.handle_bar(bar)
    assert ind.spike_count == 0


def test_volume_absent_fires_on_price_alone():
    closes = [100.0] * 25 + [100.5, 101.0, 110.0]
    volumes = [0.0] * 28
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=2.0,
    )
    for bar in _bars(closes, volumes=volumes):
        ind.handle_bar(bar)
    assert ind.volume_mode is VolumeMode.PRICE_ONLY
    assert ind.spike_count == 1


def test_cooldown_suppresses_subsequent_fires():
    # Several large back-to-back moves: without cooldown all would fire.
    closes = [100.0] * 25 + [110.0, 120.0, 130.0, 140.0]
    ind = SpikeIndicator(
        move_method=MoveMethod.NET,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=1.0,
        cooldown_bars=10,
        require_volume=VolumeMode.NEVER,
    )
    for bar in _bars(closes):
        ind.handle_bar(bar)
    assert ind.spike_count == 1  # cooldown blocked the rest


def test_reset_clears_state():
    ind = SpikeIndicator(require_volume=VolumeMode.NEVER)
    for bar in _bars([100.0, 101.0] * 20):
        ind.handle_bar(bar)
    ind._reset()
    assert ind.spike_count == 0
    assert ind.volume_mode is None
    assert ind.has_inputs is False
    assert ind.initialized is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py -v`
Expected: `handle_bar` not implemented → tests fail.

- [ ] **Step 3: Implement runtime methods**

Append to `packages/indicators/indicators/spike/indicator.py`:
```python
    def handle_bar(self, bar: Bar) -> None:
        PyCondition.not_none(bar, "bar")
        self._update(
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=float(bar.volume),
            ts_ns=bar.ts_init,
        )

    def _update(self, high: float, low: float, close: float, volume: float, ts_ns: int) -> None:
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
        # The last N+1 closes/highs/lows define the measurement window.
        closes_win = list(self._closes)[-(N + 1):]
        highs_win = list(self._highs)[-(N + 1):]
        lows_win = list(self._lows)[-(N + 1):]
        result = compute_move(
            self.move_method,
            closes=closes_win,
            highs=highs_win,
            lows=lows_win,
        )

        baseline_moves = self._baseline_moves_excluding_current()
        if len(baseline_moves) < 2:
            return  # not enough samples for stdev/median

        if not self._price_rule_passes(result.magnitude, baseline_moves):
            return

        if self.volume_mode is VolumeMode.PRICE_AND_VOLUME:
            recent_vol = sum(list(self._volumes)[-N:])
            baseline_vols = self._baseline_volumes_excluding_current()
            if len(baseline_vols) < 2:
                return
            if not self._volume_rule_passes(recent_vol, baseline_vols):
                return
            volume_ratio: float | None = (
                recent_vol / max(_baseline_centre(self.statistic, baseline_vols), 1e-12)
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
        # The current measurement window occupies the LAST N+1 entries.
        # The baseline period occupies the M entries before that, plus we need
        # one extra prior_close for the earliest baseline sample → M+N+1 total.
        # Total buffer size is M + N + 1, so all entries [0 : M] (M entries) form
        # the baseline period closes; baseline windows slide over them with one
        # prior-close drawn from indices [k : k+N+1] where k ranges 0 .. M-N.
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
        N = self.measurement_window
        M = self.baseline_window
        vols = list(self._volumes)
        out: list[float] = []
        for k in range(0, M - N + 1):
            out.append(sum(vols[k : k + N]))
        return out

    def _price_rule_passes(self, magnitude: float, baseline: list[float]) -> bool:
        return _statistic_rule_passes(self.statistic, magnitude, baseline, self.price_threshold)

    def _volume_rule_passes(self, recent: float, baseline: list[float]) -> bool:
        return _statistic_rule_passes(self.statistic, recent, baseline, self.volume_threshold)


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py tests/test_spike_moves.py -v`
Expected: all tests pass.

If `make_bar` helper import path is wrong, inspect `packages/indicators/tests/helpers/bar_factory.py` and fix the import; the helper exists per the repo layout.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/spike/indicator.py \
        packages/indicators/tests/test_spike_indicator.py
git commit -m "feat(spike): handle_bar, baseline computation, rules, cooldown, latching"
```

---

## Task 5: Parametrized variant coverage

**Files:**
- Modify: `packages/indicators/tests/test_spike_indicator.py` (add parametrized tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_spike_indicator.py`:
```python
@pytest.mark.parametrize("method", list(MoveMethod))
@pytest.mark.parametrize("stat", list(Statistic))
def test_warmup_no_fire_before_full_buffer(method, stat):
    ind = SpikeIndicator(
        move_method=method, statistic=stat,
        measurement_window=3, baseline_window=10,
        require_volume=VolumeMode.NEVER,
    )
    # Only N+M-1 bars → not enough
    for bar in _bars([100.0, 101.0] * 6):  # 12 bars, need 13
        ind.handle_bar(bar)
    assert ind.spike_count == 0


@pytest.mark.parametrize("method", list(MoveMethod))
def test_excursion_fires_on_intra_window_round_trip(method):
    # Construct a series with a tall intra-window spike that round-trips to flat.
    closes = [100.0] * 22 + [100.0, 100.0, 100.0]  # ends flat
    highs  = [100.5] * 22 + [100.5, 120.0, 100.5]  # one bar pierces 120
    lows   = [ 99.5] * 25
    ind = SpikeIndicator(
        move_method=method,
        statistic=Statistic.ZSCORE,
        measurement_window=3,
        baseline_window=20,
        price_threshold=1.5,
        require_volume=VolumeMode.NEVER,
    )
    for bar in _bars(closes, highs=highs, lows=lows):
        ind.handle_bar(bar)
    # NET sees ~0 move → no fire. EXCURSION & RANGE see ~20 → fire.
    if method is MoveMethod.NET:
        assert ind.spike_count == 0
    else:
        assert ind.spike_count >= 1
```

- [ ] **Step 2: Run tests to verify they pass (no implementation change needed)**

Run: `cd packages/indicators && uv run pytest tests/test_spike_indicator.py -v`
Expected: all parametrized cases pass. If any fail, the failure is real and must be diagnosed before proceeding.

- [ ] **Step 3: Commit**

```bash
git add packages/indicators/tests/test_spike_indicator.py
git commit -m "test(spike): parametrize variant coverage across MoveMethod and Statistic"
```

---

## Task 6: Extend `ParamSchema` with enum type (backend)

**Files:**
- Modify: `packages/server/server/store/indicators.py`
- Test: locate existing tests for the registry (likely `packages/server/tests/test_indicators_*.py`); add enum cases.

- [ ] **Step 1: Discover the existing tests**

```bash
ls packages/server/tests/ | grep -i indicator
```
Identify which file covers `INDICATOR_TYPES` / param validation. Note its path for Step 4.

- [ ] **Step 2: Write the failing test**

Append to whatever test file covers `build_indicator_from_instance` / param validation. Example:
```python
from server.store.indicators import ParamSchema, ParamValidationError

def test_param_schema_accepts_enum_type():
    schema = ParamSchema(
        name="mode", type="enum", default="A", choices=("A", "B", "C"),
    )
    assert schema.type == "enum"
    assert schema.choices == ("A", "B", "C")


def test_validate_rejects_value_outside_enum_choices():
    schema = ParamSchema(
        name="mode", type="enum", default="A", choices=("A", "B"),
    )
    # Use whatever validation helper the existing tests use; if there's a
    # validate_param or coerce_param function, call it; otherwise instantiate
    # a one-param IndicatorType and call build_indicator_from_instance with
    # an invalid value and assert ParamValidationError.
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd packages/server && uv run pytest tests/<file>.py -v`
Expected: type-checker / validation error — enum type not yet supported.

- [ ] **Step 4: Implement**

In `packages/server/server/store/indicators.py`:
- Change the `ParamSchema` dataclass:
```python
@dataclass(frozen=True)
class ParamSchema:
    name: str
    type: Literal["int", "float", "enum"]
    default: int | float | str
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    label: str | None = None
    choices: tuple[str, ...] | None = None  # required when type == "enum"
```
- In `build_indicator_from_instance`, when `schema.type == "enum"`, ensure the value is a string in `schema.choices`; otherwise raise `ParamValidationError(f"{schema.name}: {value!r} not in {schema.choices}")`.
- Numeric `min`/`max` checks must be guarded by `schema.type in ("int", "float")`.

- [ ] **Step 5: Run tests**

Run: `cd packages/server && uv run pytest tests/ -v`
Expected: new enum tests pass; existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/server/store/indicators.py packages/server/tests/<file>.py
git commit -m "feat(indicators): add enum type to ParamSchema"
```

---

## Task 7: Register `Spike` in `INDICATOR_TYPES` + `_compute_spike`

**Files:**
- Modify: `packages/server/server/store/indicators.py`
- Test: same test file as Task 6

- [ ] **Step 1: Write failing test**

```python
from server.store.indicators import INDICATOR_TYPES, compute_indicator_instance


def test_spike_registered():
    t = INDICATOR_TYPES["Spike"]
    assert t.type == "Spike"
    assert t.display == "overlay"
    param_names = {p.name for p in t.params}
    assert {"move_method", "statistic", "measurement_window", "baseline_window",
            "price_threshold", "volume_threshold", "cooldown_bars",
            "require_volume", "max_spikes"} <= param_names


def test_spike_compute_returns_sparse_series(small_bar_list):
    # small_bar_list comes from existing test fixtures
    result = compute_indicator_instance(
        instance_id="test",
        type_name="Spike",
        params={
            "move_method": "NET",
            "statistic": "ZSCORE",
            "measurement_window": 3,
            "baseline_window": 10,
            "price_threshold": 2.5,
            "volume_threshold": 2.0,
            "cooldown_bars": 10,
            "require_volume": "NEVER",
            "max_spikes": 100,
        },
        bars=small_bar_list,
    )
    assert "spike_up" in result.outputs
    assert "spike_down" in result.outputs
    assert len(result.outputs["spike_up"]) == len(small_bar_list)
```

- [ ] **Step 2: Run failing test**

Run: `cd packages/server && uv run pytest -k spike -v`
Expected: `KeyError: 'Spike'`.

- [ ] **Step 3: Implement**

In `packages/server/server/store/indicators.py`:

Import at top:
```python
from indicators.spike import SpikeIndicator
from indicators.spike.model import MoveMethod, Statistic, VolumeMode
```

Add to `INDICATOR_TYPES` (inside the dict literal, after `"ZigZag"`):
```python
    "Spike": IndicatorType(
        type="Spike",
        label_template="Spike({move_method},{statistic})",
        display="overlay",
        outputs=("spike_up", "spike_down"),
        params=(
            ParamSchema(name="move_method", type="enum", default="EXCURSION",
                        choices=("NET", "EXCURSION", "RANGE"), label="Move method"),
            ParamSchema(name="statistic", type="enum", default="ZSCORE",
                        choices=("MEAN", "MEDIAN", "ZSCORE"), label="Statistic"),
            ParamSchema(name="measurement_window", type="int", default=5,
                        min=2, max=200, label="Measurement window (N)"),
            ParamSchema(name="baseline_window", type="int", default=20,
                        min=3, max=2000, label="Baseline window (M)"),
            ParamSchema(name="price_threshold", type="float", default=2.5,
                        min=0.0, max=20.0, step=0.1, label="Price threshold"),
            ParamSchema(name="volume_threshold", type="float", default=2.0,
                        min=0.0, max=20.0, step=0.1, label="Volume threshold"),
            ParamSchema(name="cooldown_bars", type="int", default=20,
                        min=0, max=2000, label="Cooldown bars"),
            ParamSchema(name="require_volume", type="enum", default="AUTO",
                        choices=("AUTO", "ALWAYS", "NEVER"), label="Require volume"),
            ParamSchema(name="max_spikes", type="int", default=10000,
                        min=0, max=1_000_000, label="Max spikes"),
        ),
        factory=lambda p: SpikeIndicator(
            move_method=MoveMethod(p["move_method"]),
            statistic=Statistic(p["statistic"]),
            measurement_window=int(p["measurement_window"]),
            baseline_window=int(p["baseline_window"]),
            price_threshold=float(p["price_threshold"]),
            volume_threshold=float(p["volume_threshold"]),
            cooldown_bars=int(p["cooldown_bars"]),
            require_volume=VolumeMode(p["require_volume"]),
            max_spikes=int(p["max_spikes"]),
        ),
        update=update_bar,
    ),
```

Add `_compute_spike` next to `_compute_zigzag`:
```python
def _compute_spike(
    instance_id: str,
    label: str,
    indicator: IndicatorProto,
    update: UpdateFn,
    bars: list[Bar],
) -> IndicatorResult:
    """Produce sparse up/down series marking firing bars."""
    ts_to_idx: dict[int, int] = {}
    datetimes: list[str] = []
    for i, bar in enumerate(bars):
        ts_to_idx[bar.ts_init] = i
        update(indicator, bar)
        datetimes.append(_ns_to_iso(bar.ts_event))

    spike_up: list[float | None] = [None] * len(bars)
    spike_down: list[float | None] = [None] * len(bars)
    for spike in indicator.spikes:  # type: ignore[attr-defined]
        idx = ts_to_idx.get(spike.end_ts)
        if idx is None:
            continue
        if spike.direction > 0:
            spike_up[idx] = float(bars[idx].high)
        else:
            spike_down[idx] = float(bars[idx].low)

    return IndicatorResult(
        id=instance_id,
        label=label,
        display="overlay",
        outputs={"spike_up": spike_up, "spike_down": spike_down},
        datetime=datetimes,
    )
```

Wire into `compute_indicator_instance` — locate the existing `if indicator_type.type == "ZigZag"` block and add an `elif`:
```python
    if indicator_type.type == "ZigZag":
        return _compute_zigzag(...)
    if indicator_type.type == "Spike":
        return _compute_spike(
            instance_id, label, indicator, indicator_type.update, bars
        )
```

- [ ] **Step 4: Run tests**

Run: `cd packages/server && uv run pytest tests/ -v`
Expected: new Spike tests pass; all existing pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators.py packages/server/tests/<file>.py
git commit -m "feat(indicators): register Spike in INDICATOR_TYPES with enum params"
```

---

## Task 8: Frontend — extend param schema TS type + helpers

**Files:**
- Modify: `packages/client/src/types/api.ts`
- Modify: `packages/client/src/lib/indicator-params.ts`
- Test: `packages/client/src/lib/indicator-params.test.ts`

- [ ] **Step 1: Inspect current shapes**

Read `packages/client/src/types/api.ts` and `packages/client/src/lib/indicator-params.ts`. Note the existing `ParamSchema` TS shape and `coerceParams` / `validateParams` signatures.

- [ ] **Step 2: Write failing tests**

Append to `packages/client/src/lib/indicator-params.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { coerceParams, validateParams, defaultParams } from './indicator-params'
import type { ParamSchema } from '@/types/api'

const enumSchemas: ParamSchema[] = [
  { name: 'mode', type: 'enum', default: 'A', choices: ['A', 'B', 'C'] },
]

describe('enum params', () => {
  it('defaultParams uses string default', () => {
    expect(defaultParams(enumSchemas)).toEqual({ mode: 'A' })
  })
  it('coerceParams passes strings through', () => {
    expect(coerceParams(enumSchemas, { mode: 'B' })).toEqual({ mode: 'B' })
  })
  it('validateParams rejects value outside choices', () => {
    const v = validateParams(enumSchemas, { mode: 'X' })
    expect(v.ok).toBe(false)
  })
  it('validateParams accepts valid choice', () => {
    const v = validateParams(enumSchemas, { mode: 'C' })
    expect(v.ok).toBe(true)
  })
})
```

- [ ] **Step 3: Run failing tests**

Run: `cd packages/client && bun run test:unit -- indicator-params`
(or `bunx vitest run src/lib/indicator-params.test.ts`)
Expected: type errors / runtime failures.

- [ ] **Step 4: Implement**

In `packages/client/src/types/api.ts`, widen `ParamSchema`:
```ts
export type ParamSchema =
  | {
      name: string
      type: 'int' | 'float'
      default: number
      min?: number
      max?: number
      step?: number
      label?: string
    }
  | {
      name: string
      type: 'enum'
      default: string
      choices: readonly string[]
      label?: string
    }
```

(If `ParamSchema` is currently a single shape with optional fields, use the discriminated union above — it gives the form code a clean narrow.)

The `Record<string, number>` for instance params widens to `Record<string, number | string>` everywhere that touches it. Search for `Record<string, number>` in the client and update.

In `packages/client/src/lib/indicator-params.ts`:
- `defaultParams`: return `schema.type === 'enum' ? schema.default : schema.default` (the value is already correctly typed).
- `coerceParams`: for enum schemas, return the raw string (no Number()).
- `validateParams`: for enum schemas, check membership in `choices` and produce an error like `"<name> must be one of <choices>"`.

- [ ] **Step 5: Run tests**

Run: `cd packages/client && bun run test:unit && bunx tsc --noEmit`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add packages/client/src/types/api.ts \
        packages/client/src/lib/indicator-params.ts \
        packages/client/src/lib/indicator-params.test.ts
# plus any files updated to widen Record<string, number>
git commit -m "feat(client): enum-typed ParamSchema in indicator params framework"
```

---

## Task 9: Frontend — render `<Select>` for enum params

**Files:**
- Modify: `packages/client/src/components/chart/indicator-selector/IndicatorParamForm.tsx`
- Test: `packages/client/src/components/chart/indicator-selector/IndicatorParamForm.test.tsx`

- [ ] **Step 1: Inspect**

Read `IndicatorParamForm.tsx` end-to-end. Identify where it iterates `type.params.map(param => ...)` and renders the `<Input>`. That branch becomes a switch on `param.type`.

- [ ] **Step 2: Write failing tests**

Append to `IndicatorParamForm.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { IndicatorParamForm } from './IndicatorParamForm'

const spikeType = {
  type: 'Spike',
  label_template: 'Spike',
  display: 'overlay',
  outputs: [],
  params: [
    { name: 'move_method', type: 'enum', default: 'EXCURSION',
      choices: ['NET', 'EXCURSION', 'RANGE'], label: 'Move method' },
  ],
}

it('renders a select for enum params', () => {
  render(
    <IndicatorParamForm
      type={spikeType as any}
      submitLabel="Save"
      onSubmit={() => {}}
      onCancel={() => {}}
    />,
  )
  expect(screen.getByLabelText('Move method')).toBeInTheDocument()
  // shadcn Select renders an opener button — assert it's present
  // and contains the default value text
  expect(screen.getByRole('combobox')).toHaveTextContent('EXCURSION')
})
```

- [ ] **Step 3: Run failing test**

Run: `cd packages/client && bunx vitest run src/components/chart/indicator-selector/IndicatorParamForm.test.tsx`
Expected: failure — no combobox.

- [ ] **Step 4: Implement**

In `IndicatorParamForm.tsx`, change the per-param render to switch on `param.type`. For `param.type === 'enum'`, render the shadcn `<Select>` (`@/components/ui/select`) with `param.choices` as items. On change, set `rawValues[param.name]` to the chosen string. The submit-time `coerceParams` already handles strings (from Task 8). Continue rendering `<Input>` for `'int' | 'float'` as before.

Concrete shape:
```tsx
{type.params.map(param => {
  const fieldLabel = param.label ?? param.name
  if (param.type === 'enum') {
    return (
      <div key={param.name} className="space-y-1">
        <Label htmlFor={param.name}>{fieldLabel}</Label>
        <Select
          value={rawValues[param.name]}
          onValueChange={v => setRawValues({ ...rawValues, [param.name]: v })}
        >
          <SelectTrigger id={param.name}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {param.choices.map(c => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  }
  // existing <Input> branch for int / float
  ...
})}
```

- [ ] **Step 5: Run tests**

Run: `cd packages/client && bunx vitest run && bunx tsc --noEmit`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add packages/client/src/components/chart/indicator-selector/IndicatorParamForm.tsx \
        packages/client/src/components/chart/indicator-selector/IndicatorParamForm.test.tsx
git commit -m "feat(client): IndicatorParamForm renders Select for enum params"
```

---

## Task 10: Chart rendering — Spike series in `CandlestickChart`

**Files:**
- Modify: `packages/client/src/components/chart/CandlestickChart.tsx`

- [ ] **Step 1: Inspect existing series-building code**

Read `CandlestickChart.tsx`. Locate where it builds eCharts `series` from `IndicatorResult[]`. The current handling distinguishes overlays by `display === 'overlay'` and looks at output keys. Identify a similar pattern (likely a `switch` or `if-chain` on indicator `type` or on output-key names).

- [ ] **Step 2: Implement spike series**

For each `IndicatorResult` whose `outputs` contains `spike_up` / `spike_down`:
- Create a scatter series for `spike_up` (non-null entries) with symbol `triangle`, rotated up, color from per-instance color picker.
- Create a scatter series for `spike_down` (non-null entries) with symbol `triangle`, rotated down, same color.
- Tooltip formatter shows `magnitude` (we don't have it in outputs; either include it via a new output channel `magnitude` (non-null only at firing bars), or compute it in the chart from price values). For v1 keep the tooltip simple: just show "Spike (up)" / "Spike (down)" + price at fire. Magnitude / volume ratio go in a follow-up card.

(If the team prefers magnitude in the tooltip now, extend `_compute_spike` to emit a parallel `magnitude` sparse series and update `outputs` in Task 7. Skip this micro-feature for v1 unless asked.)

- [ ] **Step 3: Manual smoke test**

Run: from worktree root,
```bash
source .env.worktree
# server
(cd packages/server && .venv/bin/uvicorn server.main:app --port $WORKTREE_SERVER_PORT &) ; echo $! > .worktree-server.pid
# client
(cd packages/client && VITE_PORT=$WORKTREE_CLIENT_PORT NAUTILUS_PORT=$WORKTREE_SERVER_PORT bun run dev &) ; echo $! > .worktree-client.pid
```
Open `http://localhost:$WORKTREE_CLIENT_PORT`, pick a backtest run, add a `Spike` indicator with the defaults, verify triangles render on the chart. (This is a manual sanity check; the formal Playwright + Chrome MCP validation happens in Steps 7–8 of the orchestration, not here.)

- [ ] **Step 4: Commit**

```bash
git add packages/client/src/components/chart/CandlestickChart.tsx
git commit -m "feat(client): render Spike up/down markers on candlestick chart"
```

---

## Task 11: Playwright e2e test for Spike

**Files:**
- Create: `packages/client/e2e/spike-indicator.spec.ts`

- [ ] **Step 1: Look at an existing indicator e2e for the pattern**

```bash
ls packages/client/e2e/ | head -20
grep -l "ZigZag\|indicator" packages/client/e2e/*.ts 2>/dev/null | head -3
```
Use the pattern of an existing indicator e2e as the template (test fixtures, navigation, indicator-add flow).

- [ ] **Step 2: Write the test**

`packages/client/e2e/spike-indicator.spec.ts`:
```ts
import { test, expect } from '@playwright/test'

test('Spike indicator: add with defaults and verify markers render', async ({ page }) => {
  await page.goto('/')
  // Navigate to a known test run — copy the navigation pattern from the
  // existing ZigZag or SMA e2e in this directory.
  // Click "Add indicator" → pick "Spike" → submit defaults → assert the
  // canvas/series count increased and at least one marker is present in the DOM.
})
```

(The test body is intentionally a template — the writer must copy the run-loading and series-counting helpers from the closest existing indicator e2e. No timeouts: wait for the chart's data-loaded sentinel, never `page.waitForTimeout`.)

- [ ] **Step 3: Run headless first**

```bash
cd packages/client && bunx playwright test e2e/spike-indicator.spec.ts --project=headless
```
Expected: passes against worktree dev servers.

- [ ] **Step 4: Commit**

```bash
git add packages/client/e2e/spike-indicator.spec.ts
git commit -m "test(spike): e2e Playwright coverage"
```

---

## Self-Review Checklist

After all tasks land:

1. **Spec coverage** — every AC checkbox on the Trello card is now real code or test. Tick them by commenting them off on the card before the PR is opened.
2. **No placeholders** — search the plan above and final code for `TODO` / `TBD` / `pass  # implement` / `fill in`. Fix any.
3. **Type consistency** — `Spike` dataclass fields used in `_compute_spike` (`end_ts`, `direction`, `magnitude`, `volume_ratio`) match the dataclass exactly.
4. **Test boundaries** — unit tests in `packages/indicators/tests/` do NOT touch the server or the catalog. Server tests use fixtures only. Playwright is the only layer that touches a live backend.
5. **Functional rule** — no new classes in client TS code (Effect-TS / functional only). Backend gets enums + frozen dataclasses + the Nautilus base, matching repo convention.
