# Key Levels Phase 1: Core + Structural Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational key levels indicator system — data model, detector protocol, NautilusTrader integration, shared infrastructure (swing detection, clustering, ATR), and the first 3 structural detectors (SwingCluster, EqualHighsLows, WickRejection).

**Architecture:** Plugin-based indicator system. `KeyLevelIndicator` inherits NautilusTrader's Cython `Indicator` base class, composes `KeyLevelDetector` implementations, and exposes dual outputs: `list[KeyLevel]` for strategies and scalar summaries for the dashboard registry. Detectors are classes implementing a Protocol, using shared helpers for swing detection, clustering, and ATR.

**Tech Stack:** Python 3.14, NautilusTrader (Cython indicators), pytest, hypothesis (property-based testing)

**Spec:** `docs/superpowers/specs/2026-03-28-key-levels-indicator-design.md`

---

## Changes from v1

This plan supersedes `2026-03-28-key-levels-phase1-core-structural.md` (v1). Key differences:

| Change | v1 | v2 | Reason |
|--------|----|----|--------|
| **Package location** | `packages/server/server/store/indicators/key_levels/` | `packages/indicators/indicators/key_levels/` | Indicators must be importable by both `nautilus_strategies` and the dashboard server, without coupling to either |
| **New package** | N/A | `packages/indicators/` with its own `pyproject.toml` | Follows the same monorepo pattern as `packages/data/` |
| **Server restructure** | Task 1 restructured `indicators.py` → package | Deferred to Phase 7 (dashboard integration) | Not needed until we register key levels in the dashboard |
| **bar_factory location** | `key_levels/shared/bar_factory.py` (production code) | `packages/indicators/tests/helpers/bar_factory.py` (test code) | Test utilities should not ship with production code |
| **IndicatorConfig.kwargs** | Passed detectors via `kwargs` | Noted as future concern; dashboard registration deferred | `kwargs` is typed `dict[str, int\|float]`, can't hold detector instances |
| **max_levels parameter** | Not present | Added to `KeyLevelIndicator` | Prevents unbounded memory growth on long backtests |
| **Test location** | `packages/server/tests/test_key_levels/` | `packages/indicators/tests/` | Tests live with the package they test |
| **Task count** | 13 tasks | 12 tasks (server restructure removed) | |

---

## File Map

### New files (Phase 1)

| File | Responsibility |
|------|---------------|
| `packages/indicators/pyproject.toml` | Package config: `nautilus-automatron-indicators` |
| `packages/indicators/indicators/__init__.py` | Public API exports |
| `packages/indicators/indicators/key_levels/__init__.py` | Key levels public API |
| `packages/indicators/indicators/key_levels/model.py` | `KeyLevel`, `Source`, `SourceMeta` union, all metadata dataclasses |
| `packages/indicators/indicators/key_levels/detector.py` | `KeyLevelDetector` Protocol |
| `packages/indicators/indicators/key_levels/indicator.py` | `KeyLevelIndicator(Indicator)` |
| `packages/indicators/indicators/key_levels/shared/__init__.py` | Exports shared helpers |
| `packages/indicators/indicators/key_levels/shared/swing.py` | `Swing` dataclass, `SwingDetector` class |
| `packages/indicators/indicators/key_levels/shared/clustering.py` | `agglomerative_cluster()` function |
| `packages/indicators/indicators/key_levels/shared/atr.py` | `StreamingAtr` class |
| `packages/indicators/indicators/key_levels/detectors/__init__.py` | Exports all detector classes |
| `packages/indicators/indicators/key_levels/detectors/swing_cluster.py` | `SwingClusterDetector` |
| `packages/indicators/indicators/key_levels/detectors/equal_highs_lows.py` | `EqualHighsLowsDetector` |
| `packages/indicators/indicators/key_levels/detectors/wick_rejection.py` | `WickRejectionDetector` |
| `packages/indicators/tests/__init__.py` | Test package |
| `packages/indicators/tests/helpers/__init__.py` | Test helpers package |
| `packages/indicators/tests/helpers/bar_factory.py` | Test utility: `make_bar()`, `make_bars_from_ohlcv()` |
| `packages/indicators/tests/conftest.py` | Shared fixtures |
| `packages/indicators/tests/test_model.py` | Tests for `KeyLevel` and metadata types |
| `packages/indicators/tests/test_swing.py` | Tests for `SwingDetector` |
| `packages/indicators/tests/test_clustering.py` | Tests for `agglomerative_cluster()` |
| `packages/indicators/tests/test_atr.py` | Tests for `StreamingAtr` |
| `packages/indicators/tests/test_indicator.py` | Tests for `KeyLevelIndicator` integration |
| `packages/indicators/tests/test_swing_cluster.py` | Tests for `SwingClusterDetector` |
| `packages/indicators/tests/test_equal_highs_lows.py` | Tests for `EqualHighsLowsDetector` |
| `packages/indicators/tests/test_wick_rejection.py` | Tests for `WickRejectionDetector` |

### No modified files in Phase 1

The server's `indicators.py` is untouched. Dashboard integration (registering `KeyLevelIndicator` in the server's registry) is deferred to Phase 7.

---

### Task 1: Create the indicators package

**Files:**
- Create: `packages/indicators/pyproject.toml`
- Create: `packages/indicators/indicators/__init__.py`
- Create: `packages/indicators/indicators/key_levels/__init__.py` (empty for now)
- Create: `packages/indicators/indicators/key_levels/shared/__init__.py` (empty for now)

- [ ] **Step 1: Create package directory structure**

```bash
cd /Users/mordrax/code/nautilus_automatron/.worktrees/key-levels
mkdir -p packages/indicators/indicators/key_levels/shared
mkdir -p packages/indicators/tests/helpers
```

- [ ] **Step 2: Write pyproject.toml**

Create `packages/indicators/pyproject.toml`:

```toml
[project]
name = "nautilus-automatron-indicators"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "nautilus_trader",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "hypothesis>=6.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "hypothesis>=6.0.0",
]

[tool.hatch.build.targets.wheel]
packages = ["indicators"]

[tool.pytest.ini_options]
pythonpath = ["."]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create __init__.py files**

Create `packages/indicators/indicators/__init__.py`:

```python
"""Custom NautilusTrader indicators.

Shared indicator library usable by strategies (nautilus_strategies)
and the dashboard server (nautilus_automatron).
"""
```

Create `packages/indicators/indicators/key_levels/__init__.py` (empty):

```python
```

Create `packages/indicators/indicators/key_levels/shared/__init__.py` (empty):

```python
```

Create `packages/indicators/tests/__init__.py` (empty):

```python
```

Create `packages/indicators/tests/helpers/__init__.py` (empty):

```python
```

- [ ] **Step 4: Create venv and install**

```bash
cd packages/indicators
uv venv
uv pip install -e ".[dev]"
```

- [ ] **Step 5: Verify the package is importable**

```bash
cd packages/indicators
.venv/bin/python -c "import indicators; print('Package OK')"
```

Expected: `Package OK`

- [ ] **Step 6: Commit**

```bash
git add packages/indicators/
git commit -m "feat: create nautilus-automatron-indicators package"
```

---

### Task 2: Bar factory test utility

**Files:**
- Create: `packages/indicators/tests/helpers/bar_factory.py`
- Create: `packages/indicators/tests/conftest.py`
- Create: `packages/indicators/tests/test_bar_factory.py`

- [ ] **Step 1: Write bar_factory.py**

Create `packages/indicators/tests/helpers/bar_factory.py`:

```python
"""Test utility for creating NautilusTrader Bar objects from raw floats.

NautilusTrader Bar objects require BarType, Price, and Quantity wrapper types.
This factory abstracts that away so tests can work with plain numbers.
"""

from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import BarAggregation, PriceType
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.objects import Price, Quantity

# Default bar type used across all tests — a 1-minute bid bar on a simulated venue.
DEFAULT_BAR_TYPE = BarType(
    instrument_id=InstrumentId(Symbol("TEST"), Venue("SIM")),
    bar_specification=BarSpecification(1, BarAggregation.MINUTE, PriceType.BID),
)

# 1 hour in nanoseconds — used to space bars apart in time.
_1H_NS = 3_600_000_000_000

# Base timestamp: 2024-01-01 00:00:00 UTC in nanoseconds.
_BASE_TS = 1_704_067_200_000_000_000


def make_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
    ts_ns: int = _BASE_TS,
    bar_type: BarType = DEFAULT_BAR_TYPE,
) -> Bar:
    """Create a NautilusTrader Bar from raw floats.

    Args:
        open_: Opening price.
        high: High price.
        low: Low price.
        close: Closing price.
        volume: Volume (default 100.0).
        ts_ns: Event timestamp in nanoseconds (default 2024-01-01 00:00:00 UTC).
        bar_type: BarType specification (default TEST.SIM 1-MINUTE-BID).

    Returns:
        A NautilusTrader Bar object.
    """
    return Bar(
        bar_type=bar_type,
        open=Price.from_str(f"{open_:.5f}"),
        high=Price.from_str(f"{high:.5f}"),
        low=Price.from_str(f"{low:.5f}"),
        close=Price.from_str(f"{close:.5f}"),
        volume=Quantity.from_str(f"{volume:.2f}"),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


def make_bars_from_ohlcv(
    data: list[tuple[float, float, float, float, float]],
    start_ts: int = _BASE_TS,
    interval_ns: int = _1H_NS,
    bar_type: BarType = DEFAULT_BAR_TYPE,
) -> list[Bar]:
    """Create a list of Bars from OHLCV tuples.

    Args:
        data: List of (open, high, low, close, volume) tuples.
        start_ts: Timestamp of the first bar in nanoseconds.
        interval_ns: Time between bars in nanoseconds (default 1 hour).
        bar_type: BarType specification.

    Returns:
        List of Bar objects with incrementing timestamps.
    """
    return [
        make_bar(o, h, l, c, v, ts_ns=start_ts + i * interval_ns, bar_type=bar_type)
        for i, (o, h, l, c, v) in enumerate(data)
    ]


def make_bars_from_closes(
    closes: list[float],
    spread: float = 0.5,
    volume: float = 100.0,
    start_ts: int = _BASE_TS,
    interval_ns: int = _1H_NS,
    bar_type: BarType = DEFAULT_BAR_TYPE,
) -> list[Bar]:
    """Create Bars from a list of close prices with synthetic OHLV.

    High and low are generated symmetrically around close using `spread`.
    Open is set to the previous close (or the first close for bar 0).

    Args:
        closes: List of closing prices.
        spread: Distance from close to high/low (default 0.5).
        volume: Volume for each bar (default 100.0).
        start_ts: Timestamp of the first bar in nanoseconds.
        interval_ns: Time between bars in nanoseconds (default 1 hour).
        bar_type: BarType specification.

    Returns:
        List of Bar objects.
    """
    bars: list[Bar] = []
    for i, close in enumerate(closes):
        open_ = closes[i - 1] if i > 0 else close
        high = max(open_, close) + spread
        low = min(open_, close) - spread
        bars.append(
            make_bar(
                open_=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                ts_ns=start_ts + i * interval_ns,
                bar_type=bar_type,
            )
        )
    return bars
```

- [ ] **Step 2: Write conftest.py**

Create `packages/indicators/tests/conftest.py`:

```python
"""Shared fixtures for indicator tests."""

import pytest

from tests.helpers.bar_factory import (
    make_bar,
    make_bars_from_closes,
    make_bars_from_ohlcv,
)


@pytest.fixture
def make_bar_fn():
    """Provide the make_bar function as a fixture."""
    return make_bar


@pytest.fixture
def make_bars_from_closes_fn():
    """Provide the make_bars_from_closes function as a fixture."""
    return make_bars_from_closes


@pytest.fixture
def make_bars_from_ohlcv_fn():
    """Provide the make_bars_from_ohlcv function as a fixture."""
    return make_bars_from_ohlcv
```

- [ ] **Step 3: Write smoke test for bar_factory**

Create `packages/indicators/tests/test_bar_factory.py`:

```python
"""Tests for bar factory utility."""

import pytest

from tests.helpers.bar_factory import (
    make_bar,
    make_bars_from_closes,
    make_bars_from_ohlcv,
)


def test_make_bar_returns_correct_ohlcv():
    bar = make_bar(100.0, 105.0, 95.0, 102.0, 500.0)
    assert float(bar.open) == pytest.approx(100.0, abs=1e-4)
    assert float(bar.high) == pytest.approx(105.0, abs=1e-4)
    assert float(bar.low) == pytest.approx(95.0, abs=1e-4)
    assert float(bar.close) == pytest.approx(102.0, abs=1e-4)
    assert float(bar.volume) == pytest.approx(500.0, abs=1e-1)


def test_make_bar_timestamps():
    bar1 = make_bar(1.0, 2.0, 0.5, 1.5, ts_ns=1000)
    assert bar1.ts_event == 1000
    assert bar1.ts_init == 1000


def test_make_bars_from_ohlcv_count_and_timestamps():
    data = [
        (100.0, 105.0, 95.0, 102.0, 100.0),
        (102.0, 108.0, 100.0, 106.0, 200.0),
        (106.0, 107.0, 103.0, 104.0, 150.0),
    ]
    bars = make_bars_from_ohlcv(data, start_ts=0, interval_ns=1000)
    assert len(bars) == 3
    assert bars[0].ts_event == 0
    assert bars[1].ts_event == 1000
    assert bars[2].ts_event == 2000
    assert float(bars[1].close) == pytest.approx(106.0, abs=1e-4)


def test_make_bars_from_closes_generates_valid_bars():
    closes = [100.0, 102.0, 98.0, 103.0]
    bars = make_bars_from_closes(closes, spread=1.0)
    assert len(bars) == 4
    for bar in bars:
        assert float(bar.high) >= float(bar.low)
        assert float(bar.high) >= float(bar.close)
        assert float(bar.low) <= float(bar.close)
```

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_bar_factory.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/tests/
git commit -m "feat: add bar factory test utility for indicators"
```

---

### Task 3: KeyLevel data model and metadata types

**Files:**
- Create: `packages/indicators/indicators/key_levels/model.py`
- Create: `packages/indicators/tests/test_model.py`

- [ ] **Step 1: Write the test file**

Create `packages/indicators/tests/test_model.py`:

```python
"""Tests for KeyLevel data model and metadata types."""

import pytest
from dataclasses import FrozenInstanceError

from indicators.key_levels.model import (
    KeyLevel,
    SwingClusterMeta,
    PivotPointMeta,
    FibonacciMeta,
)


def test_key_level_is_frozen():
    level = KeyLevel(
        price=100.0,
        strength=0.8,
        bounce_count=3,
        first_seen_ts=1000,
        last_touched_ts=2000,
        zone_upper=100.5,
        zone_lower=99.5,
        source="swing_cluster",
        meta=SwingClusterMeta(cluster_radius=0.5, pivot_indices=(1, 5, 12)),
    )
    with pytest.raises(FrozenInstanceError):
        level.price = 101.0  # type: ignore[misc]


def test_key_level_equality():
    meta = SwingClusterMeta(cluster_radius=0.5, pivot_indices=(1, 5))
    level_a = KeyLevel(
        price=100.0, strength=0.8, bounce_count=2,
        first_seen_ts=0, last_touched_ts=100,
        zone_upper=100.5, zone_lower=99.5,
        source="swing_cluster", meta=meta,
    )
    level_b = KeyLevel(
        price=100.0, strength=0.8, bounce_count=2,
        first_seen_ts=0, last_touched_ts=100,
        zone_upper=100.5, zone_lower=99.5,
        source="swing_cluster", meta=meta,
    )
    assert level_a == level_b


def test_key_level_invariants():
    meta = SwingClusterMeta(cluster_radius=0.5, pivot_indices=(1,))
    level = KeyLevel(
        price=100.0, strength=0.8, bounce_count=1,
        first_seen_ts=0, last_touched_ts=100,
        zone_upper=100.5, zone_lower=99.5,
        source="swing_cluster", meta=meta,
    )
    assert level.zone_lower <= level.price <= level.zone_upper
    assert 0.0 <= level.strength <= 1.0
    assert level.first_seen_ts <= level.last_touched_ts
    assert level.bounce_count >= 0


def test_pivot_point_meta():
    meta = PivotPointMeta(
        variant="fibonacci",
        level_name="R1",
        period_high=110.0,
        period_low=90.0,
        period_close=105.0,
    )
    assert meta.variant == "fibonacci"
    assert meta.level_name == "R1"


def test_fibonacci_meta():
    meta = FibonacciMeta(
        ratio=0.618,
        swing_high=110.0,
        swing_low=90.0,
        direction="retracement",
    )
    assert meta.ratio == 0.618
    assert meta.direction == "retracement"


def test_source_literal_accepts_valid_sources():
    meta = SwingClusterMeta(cluster_radius=0.5, pivot_indices=())
    for source in ["swing_cluster", "pivot_standard", "volume_profile"]:
        level = KeyLevel(
            price=100.0, strength=0.5, bounce_count=0,
            first_seen_ts=0, last_touched_ts=0,
            zone_upper=100.5, zone_lower=99.5,
            source=source, meta=meta,
        )
        assert level.source == source
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_model.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'indicators.key_levels.model'`

- [ ] **Step 3: Write model.py**

Create `packages/indicators/indicators/key_levels/model.py` with the full content from the spec — all 22 SourceMeta dataclasses, the Source literal, and the KeyLevel dataclass. This is identical to v1 Task 3 Step 3 (see v1 plan for the complete model.py code).

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_model.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/model.py packages/indicators/tests/test_model.py
git commit -m "feat: add KeyLevel data model and typed metadata"
```

---

### Task 4: StreamingAtr helper

**Files:**
- Create: `packages/indicators/indicators/key_levels/shared/atr.py`
- Create: `packages/indicators/tests/test_atr.py`

Identical to v1 Task 4, but file paths change from `packages/server/server/store/indicators/key_levels/shared/atr.py` to `packages/indicators/indicators/key_levels/shared/atr.py`, and test imports change from `server.store.indicators.key_levels.shared.atr` to `indicators.key_levels.shared.atr`.

- [ ] **Step 1: Write the test**

Create `packages/indicators/tests/test_atr.py` — same test content as v1 Task 4 Step 1, with import changed to:

```python
from indicators.key_levels.shared.atr import StreamingAtr
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_atr.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write StreamingAtr**

Create `packages/indicators/indicators/key_levels/shared/atr.py` — identical code to v1 Task 4 Step 3.

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_atr.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/shared/atr.py packages/indicators/tests/test_atr.py
git commit -m "feat: add StreamingAtr helper for key levels"
```

---

### Task 5: SwingDetector helper

**Files:**
- Create: `packages/indicators/indicators/key_levels/shared/swing.py`
- Create: `packages/indicators/tests/test_swing.py`

Identical logic to v1 Task 5, with import paths updated to `indicators.key_levels.shared.swing`.

- [ ] **Step 1: Write the test**

Create `packages/indicators/tests/test_swing.py` — same test content as v1 Task 5 Step 1, with import:

```python
from indicators.key_levels.shared.swing import Swing, SwingDetector
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_swing.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write SwingDetector**

Create `packages/indicators/indicators/key_levels/shared/swing.py` — identical code to v1 Task 5 Step 3.

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_swing.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/shared/swing.py packages/indicators/tests/test_swing.py
git commit -m "feat: add SwingDetector (Williams fractal) for key levels"
```

---

### Task 6: Agglomerative clustering utility

**Files:**
- Create: `packages/indicators/indicators/key_levels/shared/clustering.py`
- Create: `packages/indicators/tests/test_clustering.py`

Identical logic to v1 Task 6, with import paths updated to `indicators.key_levels.shared.clustering`.

- [ ] **Step 1: Write the test**

Create `packages/indicators/tests/test_clustering.py` — same test content as v1 Task 6 Step 1, with import:

```python
from indicators.key_levels.shared.clustering import agglomerative_cluster
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_clustering.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write clustering utility**

Create `packages/indicators/indicators/key_levels/shared/clustering.py` — identical code to v1 Task 6 Step 3.

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_clustering.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/shared/clustering.py packages/indicators/tests/test_clustering.py
git commit -m "feat: add agglomerative clustering utility for key levels"
```

---

### Task 7: KeyLevelDetector protocol

**Files:**
- Create: `packages/indicators/indicators/key_levels/detector.py`

- [ ] **Step 1: Write detector.py**

Create `packages/indicators/indicators/key_levels/detector.py`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add packages/indicators/indicators/key_levels/detector.py
git commit -m "feat: add KeyLevelDetector protocol"
```

---

### Task 8: KeyLevelIndicator (NautilusTrader integration)

**Files:**
- Create: `packages/indicators/indicators/key_levels/indicator.py`
- Create: `packages/indicators/tests/test_indicator.py`

- [ ] **Step 1: Write the test**

Create `packages/indicators/tests/test_indicator.py`:

```python
"""Tests for KeyLevelIndicator — NautilusTrader integration."""

import math

import pytest

from indicators.key_levels.indicator import KeyLevelIndicator
from indicators.key_levels.model import KeyLevel, SwingClusterMeta
from tests.helpers.bar_factory import make_bar


class FakeDetector:
    """A trivial detector for testing the indicator shell."""

    def __init__(self, fixed_levels: list[KeyLevel] | None = None, warmup: int = 0):
        self._fixed_levels = fixed_levels or []
        self._warmup = warmup
        self._bar_count = 0

    @property
    def name(self):
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return self._warmup

    def update(self, bar) -> None:
        self._bar_count += 1

    def levels(self) -> list[KeyLevel]:
        if self._bar_count >= self._warmup:
            return list(self._fixed_levels)
        return []

    def reset(self) -> None:
        self._bar_count = 0


def _make_level(price: float, strength: float) -> KeyLevel:
    return KeyLevel(
        price=price,
        strength=strength,
        bounce_count=1,
        first_seen_ts=0,
        last_touched_ts=0,
        zone_upper=price + 0.5,
        zone_lower=price - 0.5,
        source="swing_cluster",
        meta=SwingClusterMeta(cluster_radius=0.5, pivot_indices=(0,)),
    )


def test_indicator_not_initialized_before_warmup():
    detector = FakeDetector(warmup=3)
    indicator = KeyLevelIndicator(detectors=[detector])
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    indicator.handle_bar(bar)
    assert not indicator.initialized


def test_indicator_initialized_after_warmup():
    detector = FakeDetector(warmup=2)
    indicator = KeyLevelIndicator(detectors=[detector])
    for i in range(2):
        indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0, ts_ns=i * 1000))
    assert indicator.initialized


def test_indicator_levels_returned():
    levels = [_make_level(100.0, 0.8), _make_level(110.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels) == 2


def test_indicator_levels_sorted_by_strength_desc():
    levels = [_make_level(100.0, 0.3), _make_level(110.0, 0.9), _make_level(105.0, 0.6)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    strengths = [l.strength for l in indicator.levels]
    assert strengths == [0.9, 0.6, 0.3]


def test_nearest_support_by_proximity():
    levels = [_make_level(90.0, 0.9), _make_level(99.0, 0.3)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert indicator.nearest_support == pytest.approx(99.0, abs=0.01)


def test_strongest_support():
    levels = [_make_level(90.0, 0.9), _make_level(99.0, 0.3)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert indicator.strongest_support == pytest.approx(90.0, abs=0.01)


def test_nearest_resistance_by_proximity():
    levels = [_make_level(101.0, 0.3), _make_level(120.0, 0.9)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert indicator.nearest_resistance == pytest.approx(101.0, abs=0.01)


def test_no_support_returns_nan():
    levels = [_make_level(110.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert math.isnan(indicator.nearest_support)
    assert math.isnan(indicator.strongest_support)


def test_levels_by_source():
    levels = [_make_level(100.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels_by_source("swing_cluster")) == 1
    assert len(indicator.levels_by_source("pivot_standard")) == 0


def test_level_count():
    levels = [_make_level(100.0, 0.5), _make_level(110.0, 0.8)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert indicator.level_count == 2.0


def test_max_levels_truncates():
    levels = [_make_level(90.0 + i, 0.1 * i) for i in range(20)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector], max_levels=5)
    indicator.handle_bar(make_bar(100.0, 105.0, 95.0, 100.0))
    assert len(indicator.levels) == 5
    # Should keep the 5 strongest
    assert indicator.levels[0].strength == pytest.approx(1.9, abs=0.01)


def test_reset():
    levels = [_make_level(100.0, 0.5)]
    detector = FakeDetector(fixed_levels=levels, warmup=0)
    indicator = KeyLevelIndicator(detectors=[detector])
    indicator.handle_bar(make_bar(105.0, 110.0, 100.0, 105.0))
    assert len(indicator.levels) == 1
    indicator.reset()
    assert indicator.levels == []
    assert not indicator.initialized
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_indicator.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write KeyLevelIndicator**

Create `packages/indicators/indicators/key_levels/indicator.py`:

```python
"""KeyLevelIndicator — NautilusTrader Indicator subclass.

Composes multiple KeyLevelDetectors and exposes dual output paths:
- .levels -> list[KeyLevel] for strategy consumption
- Scalar summary properties for dashboard/registry integration
"""

from __future__ import annotations

from nautilus_trader.indicators.base import Indicator
from nautilus_trader.model.data import Bar

from indicators.key_levels.detector import KeyLevelDetector
from indicators.key_levels.model import KeyLevel, Source


class KeyLevelIndicator(Indicator):

    def __init__(
        self,
        detectors: list[KeyLevelDetector],
        max_levels: int = 200,
    ) -> None:
        super().__init__([d.name for d in detectors])
        self._detectors = detectors
        self._max_levels = max_levels
        self._levels: list[KeyLevel] = []
        self._current_price: float = 0.0
        self._bar_count: int = 0
        self._max_warmup: int = max(
            (d.warmup_bars for d in detectors), default=0
        )

    def handle_bar(self, bar: Bar) -> None:
        self._set_has_inputs(True)
        self._bar_count += 1
        self._current_price = float(bar.close)

        for detector in self._detectors:
            detector.update(bar)

        # Merge all detector levels (no deduplication — confluence is signal)
        self._levels = []
        for detector in self._detectors:
            self._levels.extend(detector.levels())

        # Sort by strength descending
        self._levels.sort(key=lambda lvl: lvl.strength, reverse=True)

        # Enforce max levels
        if len(self._levels) > self._max_levels:
            self._levels = self._levels[: self._max_levels]

        # Initialize once all detectors have seen enough bars
        if not self.initialized and self._bar_count >= self._max_warmup:
            self._set_initialized(True)

    # -- Full collection output (for strategies) --

    @property
    def levels(self) -> list[KeyLevel]:
        return self._levels

    def levels_above(self, price: float) -> list[KeyLevel]:
        return [lvl for lvl in self._levels if lvl.price > price]

    def levels_below(self, price: float) -> list[KeyLevel]:
        return [lvl for lvl in self._levels if lvl.price < price]

    def levels_by_source(self, source: Source) -> list[KeyLevel]:
        return [lvl for lvl in self._levels if lvl.source == source]

    # -- Scalar summary outputs (for dashboard registry) --

    @property
    def nearest_support(self) -> float:
        below = self.levels_below(self._current_price)
        if not below:
            return float("nan")
        return max(below, key=lambda lvl: lvl.price).price

    @property
    def nearest_resistance(self) -> float:
        above = self.levels_above(self._current_price)
        if not above:
            return float("nan")
        return min(above, key=lambda lvl: lvl.price).price

    @property
    def strongest_support(self) -> float:
        below = self.levels_below(self._current_price)
        return below[0].price if below else float("nan")

    @property
    def strongest_resistance(self) -> float:
        above = self.levels_above(self._current_price)
        return above[0].price if above else float("nan")

    @property
    def level_count(self) -> float:
        return float(len(self._levels))

    def _reset(self) -> None:
        for detector in self._detectors:
            detector.reset()
        self._levels = []
        self._current_price = 0.0
        self._bar_count = 0
```

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_indicator.py -v
```

Expected: 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/indicator.py packages/indicators/indicators/key_levels/detector.py packages/indicators/tests/test_indicator.py
git commit -m "feat: add KeyLevelIndicator with dual output paths"
```

---

### Task 9: SwingClusterDetector

**Files:**
- Create: `packages/indicators/indicators/key_levels/detectors/__init__.py`
- Create: `packages/indicators/indicators/key_levels/detectors/swing_cluster.py`
- Create: `packages/indicators/tests/test_swing_cluster.py`

- [ ] **Step 1: Create detectors package**

```bash
mkdir -p packages/indicators/indicators/key_levels/detectors
touch packages/indicators/indicators/key_levels/detectors/__init__.py
```

- [ ] **Step 2: Write the test**

Create `packages/indicators/tests/test_swing_cluster.py` — same test logic as v1 Task 9 Step 2, with imports updated:

```python
from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from indicators.key_levels.model import SwingClusterMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS
```

(Full test code is identical to v1 Task 9 — see v1 plan for `_make_swing_bars` and all 5 test functions.)

- [ ] **Step 3: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_swing_cluster.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write SwingClusterDetector**

Create `packages/indicators/indicators/key_levels/detectors/swing_cluster.py` — same code as v1 Task 9 Step 4, with imports updated:

```python
from indicators.key_levels.model import KeyLevel, SwingClusterMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.clustering import agglomerative_cluster
from indicators.key_levels.shared.swing import SwingDetector
```

(Full implementation code is identical to v1 Task 9.)

- [ ] **Step 5: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_swing_cluster.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/indicators/indicators/key_levels/detectors/ packages/indicators/tests/test_swing_cluster.py
git commit -m "feat: add SwingClusterDetector"
```

---

### Task 10: EqualHighsLowsDetector

**Files:**
- Create: `packages/indicators/indicators/key_levels/detectors/equal_highs_lows.py`
- Create: `packages/indicators/tests/test_equal_highs_lows.py`

Identical logic to v1 Task 10, with import paths updated from `server.store.indicators.key_levels.*` to `indicators.key_levels.*` and test helpers from `tests.helpers.bar_factory`.

- [ ] **Step 1: Write the test**

Create `packages/indicators/tests/test_equal_highs_lows.py` — same test content as v1 Task 10 Step 1, with imports:

```python
from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.model import EqualHighsLowsMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_equal_highs_lows.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write EqualHighsLowsDetector**

Create `packages/indicators/indicators/key_levels/detectors/equal_highs_lows.py` — same code as v1 Task 10, with imports:

```python
from indicators.key_levels.model import EqualHighsLowsMeta, KeyLevel
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.clustering import agglomerative_cluster
from indicators.key_levels.shared.swing import SwingDetector
```

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_equal_highs_lows.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/detectors/equal_highs_lows.py packages/indicators/tests/test_equal_highs_lows.py
git commit -m "feat: add EqualHighsLowsDetector"
```

---

### Task 11: WickRejectionDetector

**Files:**
- Create: `packages/indicators/indicators/key_levels/detectors/wick_rejection.py`
- Create: `packages/indicators/tests/test_wick_rejection.py`

Identical logic to v1 Task 11, with import paths updated.

- [ ] **Step 1: Write the test**

Create `packages/indicators/tests/test_wick_rejection.py` — same test content as v1 Task 11 Step 1, with imports:

```python
from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from indicators.key_levels.model import WickRejectionMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_wick_rejection.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write WickRejectionDetector**

Create `packages/indicators/indicators/key_levels/detectors/wick_rejection.py` — same code as v1 Task 11, with imports:

```python
from indicators.key_levels.model import KeyLevel, WickRejectionMeta
from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.clustering import agglomerative_cluster
```

- [ ] **Step 4: Run tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/test_wick_rejection.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/indicators/indicators/key_levels/detectors/wick_rejection.py packages/indicators/tests/test_wick_rejection.py
git commit -m "feat: add WickRejectionDetector"
```

---

### Task 12: Package exports and full integration test

**Files:**
- Modify: `packages/indicators/indicators/__init__.py`
- Modify: `packages/indicators/indicators/key_levels/__init__.py`
- Modify: `packages/indicators/indicators/key_levels/shared/__init__.py`
- Modify: `packages/indicators/indicators/key_levels/detectors/__init__.py`
- Modify: `packages/indicators/tests/test_indicator.py` (add end-to-end test)

- [ ] **Step 1: Set up package exports**

Update `packages/indicators/indicators/key_levels/shared/__init__.py`:

```python
"""Shared helpers for key level detection."""

from indicators.key_levels.shared.atr import StreamingAtr
from indicators.key_levels.shared.clustering import agglomerative_cluster
from indicators.key_levels.shared.swing import Swing, SwingDetector

__all__ = ["StreamingAtr", "agglomerative_cluster", "Swing", "SwingDetector"]
```

Update `packages/indicators/indicators/key_levels/detectors/__init__.py`:

```python
"""Key level detector implementations."""

from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector

__all__ = ["SwingClusterDetector", "EqualHighsLowsDetector", "WickRejectionDetector"]
```

Update `packages/indicators/indicators/key_levels/__init__.py`:

```python
"""Key Levels indicator system.

Plugin-based indicator for detecting horizontal price levels (support/resistance)
through multiple independent detection methods.
"""

from indicators.key_levels.detector import KeyLevelDetector
from indicators.key_levels.indicator import KeyLevelIndicator
from indicators.key_levels.model import KeyLevel, Source, SourceMeta

__all__ = ["KeyLevel", "KeyLevelDetector", "KeyLevelIndicator", "Source", "SourceMeta"]
```

Update `packages/indicators/indicators/__init__.py`:

```python
"""Custom NautilusTrader indicators.

Shared indicator library usable by strategies (nautilus_strategies)
and the dashboard server (nautilus_automatron).
"""

from indicators.key_levels import KeyLevel, KeyLevelDetector, KeyLevelIndicator

__all__ = ["KeyLevel", "KeyLevelDetector", "KeyLevelIndicator"]
```

- [ ] **Step 2: Add end-to-end integration test with real detectors**

Append to `packages/indicators/tests/test_indicator.py`:

```python
# --- End-to-end with real detectors ---

from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from tests.helpers.bar_factory import _BASE_TS, _1H_NS


def _make_realistic_bars():
    """Create a realistic price series with swings and wick rejections."""
    data = []
    # 14 warmup bars around 100
    for i in range(14):
        data.append((100.0, 102.0, 98.0, 100.0, 100.0))

    # Swing up to 115
    for p in [102, 105, 108, 112, 115, 112, 108]:
        data.append((float(p - 1), float(p + 1), float(p - 2), float(p), 100.0))

    # Wick rejection at 105 (long lower wick)
    data.append((107.0, 108.0, 105.0, 107.5, 100.0))

    # Swing down to 90
    for p in [105, 102, 98, 95, 90, 93, 96]:
        data.append((float(p + 1), float(p + 2), float(p - 1), float(p), 100.0))

    # Swing back up
    for p in [99, 103, 107, 114, 110, 106]:
        data.append((float(p - 1), float(p + 1), float(p - 2), float(p), 100.0))

    from tests.helpers.bar_factory import make_bars_from_ohlcv
    return make_bars_from_ohlcv(data)


def test_end_to_end_with_real_detectors():
    """Full integration: KeyLevelIndicator with SwingCluster + WickRejection."""
    detectors = [
        SwingClusterDetector(period=2, cluster_distance=1.5),
        WickRejectionDetector(min_wick_ratio=1.5, zone_atr_multiple=1.0, min_rejections=1),
    ]
    indicator = KeyLevelIndicator(detectors=detectors)
    bars = _make_realistic_bars()
    for bar in bars:
        indicator.handle_bar(bar)

    # Should have found some levels
    assert len(indicator.levels) > 0

    # All levels should satisfy invariants
    for level in indicator.levels:
        assert level.zone_lower <= level.price <= level.zone_upper
        assert 0.0 <= level.strength <= 1.0
        assert level.bounce_count >= 0
        assert level.first_seen_ts <= level.last_touched_ts

    # Scalar summaries should be available
    assert not math.isnan(indicator.level_count)
    assert indicator.level_count > 0
```

- [ ] **Step 3: Run all tests**

```bash
cd packages/indicators && .venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/indicators/
git commit -m "feat: complete Phase 1 key levels — exports and integration test"
```
