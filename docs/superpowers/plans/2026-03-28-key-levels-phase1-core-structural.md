# Key Levels Phase 1: Core + Structural Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational key levels indicator system — data model, detector protocol, NautilusTrader integration, shared infrastructure (swing detection, clustering, ATR), and the first 3 structural detectors (SwingCluster, EqualHighsLows, WickRejection).

**Architecture:** Plugin-based indicator system. `KeyLevelIndicator` inherits NautilusTrader's Cython `Indicator` base class, composes `KeyLevelDetector` implementations, and exposes dual outputs: `list[KeyLevel]` for strategies and scalar summaries for the dashboard registry. Detectors are classes implementing a Protocol, using shared helpers for swing detection, clustering, and ATR.

**Tech Stack:** Python 3.14, NautilusTrader (Cython indicators), pytest, hypothesis (property-based testing)

**Spec:** `docs/superpowers/specs/2026-03-28-key-levels-indicator-design.md`

---

## File Map

### New files (Phase 1)

| File | Responsibility |
|------|---------------|
| `packages/server/server/store/indicators/__init__.py` | Re-exports from `registry.py` for backwards compatibility |
| `packages/server/server/store/indicators/registry.py` | Existing `INDICATOR_REGISTRY`, `compute_indicator`, etc. (moved from `indicators.py`) |
| `packages/server/server/store/indicators/key_levels/__init__.py` | Public API: exports `KeyLevel`, `KeyLevelIndicator`, detector classes |
| `packages/server/server/store/indicators/key_levels/model.py` | `KeyLevel`, `Source`, `SourceMeta` union, all metadata dataclasses |
| `packages/server/server/store/indicators/key_levels/detector.py` | `KeyLevelDetector` Protocol |
| `packages/server/server/store/indicators/key_levels/indicator.py` | `KeyLevelIndicator(Indicator)` |
| `packages/server/server/store/indicators/key_levels/shared/__init__.py` | Exports shared helpers |
| `packages/server/server/store/indicators/key_levels/shared/swing.py` | `Swing` dataclass, `SwingDetector` class |
| `packages/server/server/store/indicators/key_levels/shared/clustering.py` | `agglomerative_cluster()` function |
| `packages/server/server/store/indicators/key_levels/shared/atr.py` | `StreamingAtr` class |
| `packages/server/server/store/indicators/key_levels/shared/bar_factory.py` | Test utility: `make_bar()`, `make_bars_from_ohlcv()` |
| `packages/server/server/store/indicators/key_levels/detectors/__init__.py` | Exports all detector classes |
| `packages/server/server/store/indicators/key_levels/detectors/swing_cluster.py` | `SwingClusterDetector` |
| `packages/server/server/store/indicators/key_levels/detectors/equal_highs_lows.py` | `EqualHighsLowsDetector` |
| `packages/server/server/store/indicators/key_levels/detectors/wick_rejection.py` | `WickRejectionDetector` |
| `packages/server/tests/test_key_levels/__init__.py` | Test package |
| `packages/server/tests/test_key_levels/conftest.py` | Shared fixtures |
| `packages/server/tests/test_key_levels/test_model.py` | Tests for `KeyLevel` and metadata types |
| `packages/server/tests/test_key_levels/test_swing.py` | Tests for `SwingDetector` |
| `packages/server/tests/test_key_levels/test_clustering.py` | Tests for `agglomerative_cluster()` |
| `packages/server/tests/test_key_levels/test_atr.py` | Tests for `StreamingAtr` |
| `packages/server/tests/test_key_levels/test_indicator.py` | Tests for `KeyLevelIndicator` integration |
| `packages/server/tests/test_key_levels/test_swing_cluster.py` | Tests for `SwingClusterDetector` |
| `packages/server/tests/test_key_levels/test_equal_highs_lows.py` | Tests for `EqualHighsLowsDetector` |
| `packages/server/tests/test_key_levels/test_wick_rejection.py` | Tests for `WickRejectionDetector` |
| `packages/server/tests/test_key_levels/test_registry_integration.py` | Tests for `compute_indicator` pipeline with `update_bar` |

### Modified files

| File | Change |
|------|--------|
| `packages/server/server/store/indicators.py` | Deleted — content moves to `indicators/registry.py` |
| `packages/server/server/routes/indicators.py` | Update import path (from `server.store.indicators` → same, via `__init__.py` re-exports) |

---

### Task 1: Restructure indicators.py into a package

**Files:**
- Create: `packages/server/server/store/indicators/__init__.py`
- Create: `packages/server/server/store/indicators/registry.py`
- Delete: `packages/server/server/store/indicators.py`

- [ ] **Step 1: Create the indicators package directory**

```bash
cd packages/server && mkdir -p server/store/indicators
```

- [ ] **Step 2: Move existing indicators.py to registry.py**

```bash
cd packages/server && mv server/store/indicators.py server/store/indicators/registry.py
```

- [ ] **Step 3: Create __init__.py with re-exports for backwards compatibility**

Create `packages/server/server/store/indicators/__init__.py`:

```python
"""Indicator registry and key levels system.

Re-exports from registry.py to maintain backwards-compatible import paths.
"""

from server.store.indicators.registry import (
    INDICATOR_REGISTRY,
    Display,
    IndicatorConfig,
    IndicatorMeta,
    IndicatorProto,
    IndicatorResult,
    UpdateFn,
    compute_indicator,
    list_available_indicators,
    update_close,
    update_hl,
    update_hlc,
)

__all__ = [
    "INDICATOR_REGISTRY",
    "Display",
    "IndicatorConfig",
    "IndicatorMeta",
    "IndicatorProto",
    "IndicatorResult",
    "UpdateFn",
    "compute_indicator",
    "list_available_indicators",
    "update_close",
    "update_hl",
    "update_hlc",
]
```

- [ ] **Step 4: Verify existing tests still pass**

```bash
cd packages/server && python -m pytest tests/ -v
```

Expected: All existing tests pass (imports unchanged due to re-exports).

- [ ] **Step 5: Verify the server starts**

```bash
cd packages/server && python -c "from server.store.indicators import INDICATOR_REGISTRY, compute_indicator; print(f'Registry has {len(INDICATOR_REGISTRY)} indicators')"
```

Expected: `Registry has 10 indicators`

- [ ] **Step 6: Commit**

```bash
git add packages/server/server/store/indicators/ && git rm packages/server/server/store/indicators.py && git add -u
git commit -m "refactor: restructure indicators.py into package with registry.py"
```

---

### Task 2: Bar factory test utility

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/__init__.py` (empty for now)
- Create: `packages/server/server/store/indicators/key_levels/shared/__init__.py` (empty for now)
- Create: `packages/server/server/store/indicators/key_levels/shared/bar_factory.py`
- Create: `packages/server/tests/test_key_levels/__init__.py`
- Create: `packages/server/tests/test_key_levels/conftest.py`

- [ ] **Step 1: Create package directories**

```bash
cd packages/server && mkdir -p server/store/indicators/key_levels/shared && touch server/store/indicators/key_levels/__init__.py && touch server/store/indicators/key_levels/shared/__init__.py
```

- [ ] **Step 2: Write bar_factory.py**

Create `packages/server/server/store/indicators/key_levels/shared/bar_factory.py`:

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

- [ ] **Step 3: Create test directory and conftest**

```bash
cd packages/server && mkdir -p tests/test_key_levels
```

Create `packages/server/tests/test_key_levels/__init__.py` (empty file):

```python
```

Create `packages/server/tests/test_key_levels/conftest.py`:

```python
"""Shared fixtures for key levels tests."""

import pytest

from server.store.indicators.key_levels.shared.bar_factory import (
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

- [ ] **Step 4: Write a smoke test for bar_factory**

Create `packages/server/tests/test_key_levels/test_bar_factory.py`:

```python
"""Tests for bar factory utility."""

import pytest

from server.store.indicators.key_levels.shared.bar_factory import (
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

- [ ] **Step 5: Run the test**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_bar_factory.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/ packages/server/tests/test_key_levels/
git commit -m "feat: add bar factory test utility for key levels"
```

---

### Task 3: KeyLevel data model and metadata types

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/model.py`
- Create: `packages/server/tests/test_key_levels/test_model.py`

- [ ] **Step 1: Write the test file**

Create `packages/server/tests/test_key_levels/test_model.py`:

```python
"""Tests for KeyLevel data model and metadata types."""

import pytest
from dataclasses import FrozenInstanceError

from server.store.indicators.key_levels.model import (
    KeyLevel,
    SwingClusterMeta,
    PivotPointMeta,
    FibonacciMeta,
    Source,
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
    """Verify that Source literal values are accepted in KeyLevel construction."""
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
cd packages/server && python -m pytest tests/test_key_levels/test_model.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'server.store.indicators.key_levels.model'`

- [ ] **Step 3: Write model.py**

Create `packages/server/server/store/indicators/key_levels/model.py`:

```python
"""Key Level data model and typed metadata.

All types are frozen dataclasses — immutable once created.
The SourceMeta discriminated union provides type-safe, per-detector metadata
without dict[str, Any] or mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

# ---------------------------------------------------------------------------
# Source — which detector produced a level
# ---------------------------------------------------------------------------

Source = Literal[
    "swing_cluster",
    "equal_highs_lows",
    "wick_rejection",
    "pivot_standard",
    "pivot_fibonacci",
    "pivot_camarilla",
    "pivot_woodie",
    "pivot_demark",
    "fib_retracement",
    "fib_extension",
    "psychological",
    "atr_volatility",
    "volume_profile",
    "volume_distribution",
    "anchored_vwap",
    "cvd",
    "session_level",
    "periodic_level",
    "opening_range",
    "market_profile_tpo",
    "order_block",
    "fair_value_gap",
    "price_gap",
    "darvas_box",
    "consolidation_zone",
    "ma_confluence",
    "wyckoff_zone",
]

# ---------------------------------------------------------------------------
# Typed metadata per detector (discriminated union)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwingClusterMeta:
    cluster_radius: float
    pivot_indices: tuple[int, ...]


@dataclass(frozen=True)
class EqualHighsLowsMeta:
    touch_prices: tuple[float, ...]
    side: Literal["high", "low"]


@dataclass(frozen=True)
class WickRejectionMeta:
    rejection_count: int
    avg_wick_ratio: float


@dataclass(frozen=True)
class PivotPointMeta:
    variant: Literal["standard", "fibonacci", "camarilla", "woodie", "demark"]
    level_name: str
    period_high: float
    period_low: float
    period_close: float


@dataclass(frozen=True)
class FibonacciMeta:
    ratio: float
    swing_high: float
    swing_low: float
    direction: Literal["retracement", "extension"]


@dataclass(frozen=True)
class PsychologicalMeta:
    tier: Literal["major", "minor", "micro"]
    round_value: float


@dataclass(frozen=True)
class AtrVolatilityMeta:
    atr_value: float
    multiplier: float
    anchor_price: float


@dataclass(frozen=True)
class VolumeProfileMeta:
    volume_concentration: float
    node_type: Literal["poc", "hvn", "lvn", "va_high", "va_low"]
    bin_volume: float


@dataclass(frozen=True)
class VolumeDistributionMeta:
    context: Literal["consolidation", "peak", "trough", "range"]
    volume_concentration: float
    context_bar_count: int


@dataclass(frozen=True)
class AnchoredVwapMeta:
    anchor_ts: int
    anchor_type: Literal["swing_high", "swing_low", "gap", "volume_spike"]
    cumulative_volume: float


@dataclass(frozen=True)
class CvdMeta:
    cvd_value: float
    divergence: Literal["bullish", "bearish", "none"]


@dataclass(frozen=True)
class SessionLevelMeta:
    session: Literal["asian", "london", "new_york", "custom"]
    level_type: Literal["high", "low"]
    session_date: date


@dataclass(frozen=True)
class PeriodicLevelMeta:
    period: Literal["daily", "weekly", "monthly"]
    level_type: Literal["high", "low", "close"]
    period_start: date


@dataclass(frozen=True)
class OpeningRangeMeta:
    range_minutes: int
    level_type: Literal["high", "low"]


@dataclass(frozen=True)
class MarketProfileMeta:
    tpo_count: int
    node_type: Literal["poc", "va_high", "va_low"]
    total_tpo_periods: int


@dataclass(frozen=True)
class OrderBlockMeta:
    side: Literal["bullish", "bearish"]
    displacement_atr_multiple: float
    block_open: float
    block_close: float


@dataclass(frozen=True)
class FairValueGapMeta:
    side: Literal["bullish", "bearish"]
    gap_size: float
    fill_percentage: float


@dataclass(frozen=True)
class PriceGapMeta:
    gap_type: Literal["breakaway", "runaway", "exhaustion", "common"]
    gap_size: float
    fill_percentage: float
    level_type: Literal["upper", "lower"]


@dataclass(frozen=True)
class DarvasBoxMeta:
    box_top: float
    box_bottom: float
    confirmed: bool
    bars_in_box: int


@dataclass(frozen=True)
class ConsolidationZoneMeta:
    range_high: float
    range_low: float
    slope: float
    bar_count: int


@dataclass(frozen=True)
class MaConfluenceMeta:
    converging_periods: tuple[int, ...]
    spread_percent: float


@dataclass(frozen=True)
class WyckoffZoneMeta:
    phase: Literal["accumulation", "distribution"]
    event: Literal["sc", "ar", "st", "spring", "upthrust", "sos", "lpsy"]
    zone_high: float
    zone_low: float


SourceMeta = (
    SwingClusterMeta
    | EqualHighsLowsMeta
    | WickRejectionMeta
    | PivotPointMeta
    | FibonacciMeta
    | PsychologicalMeta
    | AtrVolatilityMeta
    | VolumeProfileMeta
    | VolumeDistributionMeta
    | AnchoredVwapMeta
    | CvdMeta
    | SessionLevelMeta
    | PeriodicLevelMeta
    | OpeningRangeMeta
    | MarketProfileMeta
    | OrderBlockMeta
    | FairValueGapMeta
    | PriceGapMeta
    | DarvasBoxMeta
    | ConsolidationZoneMeta
    | MaConfluenceMeta
    | WyckoffZoneMeta
)

# ---------------------------------------------------------------------------
# KeyLevel — the core output type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyLevel:
    price: float
    strength: float
    bounce_count: int
    first_seen_ts: int
    last_touched_ts: int
    zone_upper: float
    zone_lower: float
    source: Source
    meta: SourceMeta
```

- [ ] **Step 4: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_model.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/model.py packages/server/tests/test_key_levels/test_model.py
git commit -m "feat: add KeyLevel data model and typed metadata"
```

---

### Task 4: StreamingAtr helper

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/shared/atr.py`
- Create: `packages/server/tests/test_key_levels/test_atr.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_atr.py`:

```python
"""Tests for streaming ATR helper."""

import pytest

from server.store.indicators.key_levels.shared.atr import StreamingAtr


def test_atr_not_ready_before_warmup():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)
    assert not atr.ready
    assert atr.value == 0.0


def test_atr_ready_after_warmup():
    atr = StreamingAtr(period=3)
    # Bar 1: TR = 10 (no previous close, TR = high - low)
    atr.update(high=105.0, low=95.0, close=100.0)
    # Bar 2: TR = max(110-98, |110-100|, |98-100|) = 12
    atr.update(high=110.0, low=98.0, close=105.0)
    # Bar 3: TR = max(108-100, |108-105|, |100-105|) = 8
    atr.update(high=108.0, low=100.0, close=103.0)
    assert atr.ready
    assert atr.value == pytest.approx(10.0, abs=0.01)  # SMA of [10, 12, 8] = 10


def test_atr_wilder_smoothing_after_warmup():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)   # TR=10
    atr.update(high=110.0, low=98.0, close=105.0)   # TR=12
    atr.update(high=108.0, low=100.0, close=103.0)  # TR=8, ATR=10.0
    # Bar 4: TR = max(106-101, |106-103|, |101-103|) = 5
    # Wilder: ATR = (10.0 * 2 + 5) / 3 = 25/3 ≈ 8.333
    atr.update(high=106.0, low=101.0, close=104.0)
    assert atr.value == pytest.approx(25.0 / 3.0, abs=0.01)


def test_atr_reset():
    atr = StreamingAtr(period=3)
    atr.update(high=105.0, low=95.0, close=100.0)
    atr.update(high=110.0, low=98.0, close=105.0)
    atr.update(high=108.0, low=100.0, close=103.0)
    assert atr.ready
    atr.reset()
    assert not atr.ready
    assert atr.value == 0.0


def test_atr_deterministic():
    """Same inputs produce same outputs on two separate instances."""
    bars = [
        (105.0, 95.0, 100.0),
        (110.0, 98.0, 105.0),
        (108.0, 100.0, 103.0),
        (106.0, 101.0, 104.0),
    ]
    atr_a = StreamingAtr(period=3)
    atr_b = StreamingAtr(period=3)
    for h, l, c in bars:
        atr_a.update(h, l, c)
        atr_b.update(h, l, c)
    assert atr_a.value == atr_b.value
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_atr.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write StreamingAtr**

Create `packages/server/server/store/indicators/key_levels/shared/atr.py`:

```python
"""Streaming Average True Range (ATR) with Wilder smoothing.

Used by many detectors for adaptive thresholds and zone widths.
"""

from collections import deque


class StreamingAtr:
    """ATR using Wilder's smoothing method (same as NautilusTrader's ATR).

    First `period` bars use SMA for the initial ATR value.
    Subsequent bars use Wilder smoothing: ATR = (prev_ATR * (period-1) + TR) / period.
    """

    def __init__(self, period: int) -> None:
        self._period = period
        self._prev_close: float | None = None
        self._tr_buffer: deque[float] = deque(maxlen=period)
        self._value: float = 0.0
        self._ready: bool = False
        self._count: int = 0

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def value(self) -> float:
        return self._value

    def update(self, high: float, low: float, close: float) -> None:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close),
            )

        self._prev_close = close
        self._count += 1

        if not self._ready:
            self._tr_buffer.append(tr)
            if self._count >= self._period:
                self._value = sum(self._tr_buffer) / self._period
                self._ready = True
        else:
            # Wilder smoothing
            self._value = (self._value * (self._period - 1) + tr) / self._period

    def reset(self) -> None:
        self._prev_close = None
        self._tr_buffer.clear()
        self._value = 0.0
        self._ready = False
        self._count = 0
```

- [ ] **Step 4: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_atr.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/shared/atr.py packages/server/tests/test_key_levels/test_atr.py
git commit -m "feat: add StreamingAtr helper for key levels"
```

---

### Task 5: SwingDetector helper

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/shared/swing.py`
- Create: `packages/server/tests/test_key_levels/test_swing.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_swing.py`:

```python
"""Tests for SwingDetector (Williams fractal detection)."""

import pytest

from server.store.indicators.key_levels.shared.swing import Swing, SwingDetector


def test_swing_detector_no_swings_before_warmup():
    sd = SwingDetector(period=2)
    sd.update(high=100.0, low=90.0, bar_index=0, ts=0)
    sd.update(high=105.0, low=95.0, bar_index=1, ts=1000)
    assert sd.swings() == []


def test_swing_detector_finds_fractal_high():
    """A fractal high with period=2 requires bar[i].high > all 4 surrounding bars."""
    sd = SwingDetector(period=2)
    # bars: low, higher, HIGHEST, lower, lowest
    highs = [100.0, 105.0, 110.0, 105.0, 100.0]
    lows = [95.0, 100.0, 105.0, 100.0, 95.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)

    swings = sd.swings()
    swing_highs = [s for s in swings if s.side == "high"]
    assert len(swing_highs) == 1
    assert swing_highs[0].price == 110.0
    assert swing_highs[0].bar_index == 2


def test_swing_detector_finds_fractal_low():
    sd = SwingDetector(period=2)
    # bars: high, lower, LOWEST, higher, high
    highs = [110.0, 105.0, 100.0, 105.0, 110.0]
    lows = [100.0, 95.0, 90.0, 95.0, 100.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)

    swings = sd.swings()
    swing_lows = [s for s in swings if s.side == "low"]
    assert len(swing_lows) == 1
    assert swing_lows[0].price == 90.0
    assert swing_lows[0].bar_index == 2


def test_swing_detector_period_3():
    """Period=3 means the center bar must be higher/lower than 3 bars on each side."""
    sd = SwingDetector(period=3)
    # Need 7 bars: 3 ascending + peak + 3 descending
    highs = [100.0, 103.0, 106.0, 110.0, 106.0, 103.0, 100.0]
    lows = [95.0, 98.0, 101.0, 105.0, 101.0, 98.0, 95.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)

    swing_highs = [s for s in sd.swings() if s.side == "high"]
    assert len(swing_highs) == 1
    assert swing_highs[0].bar_index == 3


def test_swing_detector_multiple_swings():
    sd = SwingDetector(period=2)
    # Up-down-up pattern: swing high at bar 2, swing low at bar 4, swing high at bar 6
    highs = [100, 105, 110, 105, 100, 105, 110, 105, 100]
    lows = [95, 100, 105, 100, 95, 100, 105, 100, 95]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=float(h), low=float(l), bar_index=i, ts=i * 1000)

    swings = sd.swings()
    assert len(swings) >= 2  # At least one high and one low


def test_swing_detector_reset():
    sd = SwingDetector(period=2)
    highs = [100.0, 105.0, 110.0, 105.0, 100.0]
    lows = [95.0, 100.0, 105.0, 100.0, 95.0]
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd.update(high=h, low=l, bar_index=i, ts=i * 1000)
    assert len(sd.swings()) > 0
    sd.reset()
    assert sd.swings() == []


def test_swing_detector_deterministic():
    highs = [100.0, 105.0, 110.0, 105.0, 100.0, 95.0, 100.0]
    lows = [95.0, 100.0, 105.0, 100.0, 95.0, 90.0, 95.0]
    sd_a = SwingDetector(period=2)
    sd_b = SwingDetector(period=2)
    for i, (h, l) in enumerate(zip(highs, lows)):
        sd_a.update(high=h, low=l, bar_index=i, ts=i * 1000)
        sd_b.update(high=h, low=l, bar_index=i, ts=i * 1000)
    assert sd_a.swings() == sd_b.swings()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_swing.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write SwingDetector**

Create `packages/server/server/store/indicators/key_levels/shared/swing.py`:

```python
"""Williams fractal swing detection.

A fractal high at bar[i] means bar[i].high is greater than the highs of
the `period` bars on each side. A fractal low is the mirror.

The detector has an inherent lag of `period` bars — a swing at bar[i]
can only be confirmed once bar[i + period] has been received.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Swing:
    price: float
    bar_index: int
    ts: int
    side: Literal["high", "low"]


class SwingDetector:
    """Detects fractal swing highs and lows with configurable lookback.

    Args:
        period: Number of bars on each side of the fractal center.
                A fractal high at bar[i] requires bar[i].high > bar[j].high
                for all j in [i-period, i+period] where j != i.
                Default Williams fractal uses period=2 (5-bar pattern).
    """

    def __init__(self, period: int = 2) -> None:
        self._period = period
        self._window_size = 2 * period + 1
        # Store (high, low, bar_index, ts) for each bar in the window
        self._highs: deque[float] = deque(maxlen=self._window_size)
        self._lows: deque[float] = deque(maxlen=self._window_size)
        self._indices: deque[int] = deque(maxlen=self._window_size)
        self._timestamps: deque[int] = deque(maxlen=self._window_size)
        self._swings: list[Swing] = []

    @property
    def warmup_bars(self) -> int:
        return self._window_size

    def update(self, high: float, low: float, bar_index: int, ts: int) -> Swing | None:
        """Add a new bar and check if the center bar is now a confirmed fractal.

        Returns the newly confirmed Swing if one was detected, else None.
        """
        self._highs.append(high)
        self._lows.append(low)
        self._indices.append(bar_index)
        self._timestamps.append(ts)

        if len(self._highs) < self._window_size:
            return None

        center = self._period
        center_high = self._highs[center]
        center_low = self._lows[center]

        detected: Swing | None = None

        # Check fractal high
        is_fractal_high = all(
            center_high > self._highs[j]
            for j in range(self._window_size)
            if j != center
        )
        if is_fractal_high:
            swing = Swing(
                price=center_high,
                bar_index=self._indices[center],
                ts=self._timestamps[center],
                side="high",
            )
            self._swings.append(swing)
            detected = swing

        # Check fractal low
        is_fractal_low = all(
            center_low < self._lows[j]
            for j in range(self._window_size)
            if j != center
        )
        if is_fractal_low:
            swing = Swing(
                price=center_low,
                bar_index=self._indices[center],
                ts=self._timestamps[center],
                side="low",
            )
            self._swings.append(swing)
            detected = swing

        return detected

    def swings(self) -> list[Swing]:
        return list(self._swings)

    def reset(self) -> None:
        self._highs.clear()
        self._lows.clear()
        self._indices.clear()
        self._timestamps.clear()
        self._swings.clear()
```

- [ ] **Step 4: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_swing.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/shared/swing.py packages/server/tests/test_key_levels/test_swing.py
git commit -m "feat: add SwingDetector (Williams fractal) for key levels"
```

---

### Task 6: Agglomerative clustering utility

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/shared/clustering.py`
- Create: `packages/server/tests/test_key_levels/test_clustering.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_clustering.py`:

```python
"""Tests for agglomerative clustering utility."""

import pytest

from server.store.indicators.key_levels.shared.clustering import agglomerative_cluster


def test_empty_input():
    assert agglomerative_cluster([], merge_distance=1.0) == []


def test_single_value():
    result = agglomerative_cluster([100.0], merge_distance=1.0)
    assert len(result) == 1
    assert result[0] == ([100.0], 100.0)


def test_two_close_values_merge():
    result = agglomerative_cluster([100.0, 100.3], merge_distance=0.5)
    assert len(result) == 1
    prices, centroid = result[0]
    assert set(prices) == {100.0, 100.3}
    assert centroid == pytest.approx(100.15, abs=0.01)


def test_two_far_values_stay_separate():
    result = agglomerative_cluster([100.0, 110.0], merge_distance=0.5)
    assert len(result) == 2


def test_three_clusters():
    # Three groups: around 100, around 110, around 120
    values = [99.8, 100.0, 100.2, 109.9, 110.1, 119.8, 120.0, 120.3]
    result = agglomerative_cluster(values, merge_distance=1.0)
    assert len(result) == 3
    centroids = sorted(c for _, c in result)
    assert centroids[0] == pytest.approx(100.0, abs=0.5)
    assert centroids[1] == pytest.approx(110.0, abs=0.5)
    assert centroids[2] == pytest.approx(120.0, abs=0.5)


def test_all_same_value():
    result = agglomerative_cluster([100.0, 100.0, 100.0], merge_distance=0.5)
    assert len(result) == 1
    prices, centroid = result[0]
    assert len(prices) == 3
    assert centroid == 100.0


def test_deterministic():
    values = [99.8, 100.0, 100.2, 109.9, 110.1]
    result_a = agglomerative_cluster(values, merge_distance=1.0)
    result_b = agglomerative_cluster(values, merge_distance=1.0)
    assert result_a == result_b
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_clustering.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write clustering utility**

Create `packages/server/server/store/indicators/key_levels/shared/clustering.py`:

```python
"""Agglomerative clustering for grouping nearby price levels.

Simple 1D bottom-up clustering: start with each value as its own cluster,
iteratively merge the two closest clusters until the minimum distance
between any two clusters exceeds merge_distance.
"""

from __future__ import annotations


def agglomerative_cluster(
    values: list[float],
    merge_distance: float,
) -> list[tuple[list[float], float]]:
    """Cluster 1D values using agglomerative (bottom-up) clustering.

    Args:
        values: List of float values to cluster.
        merge_distance: Maximum distance between cluster centroids to merge.

    Returns:
        List of (members, centroid) tuples, sorted by centroid.
        Each member list contains the original values in that cluster.
    """
    if not values:
        return []

    # Initialize: each value is its own cluster
    clusters: list[list[float]] = [[v] for v in sorted(values)]

    while len(clusters) > 1:
        # Find the pair of adjacent clusters with smallest centroid distance.
        # Since clusters are sorted by centroid, the closest pair is always adjacent.
        best_dist = float("inf")
        best_idx = -1
        for i in range(len(clusters) - 1):
            centroid_i = sum(clusters[i]) / len(clusters[i])
            centroid_j = sum(clusters[i + 1]) / len(clusters[i + 1])
            dist = abs(centroid_j - centroid_i)
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_dist > merge_distance:
            break

        # Merge the two closest clusters
        merged = clusters[best_idx] + clusters[best_idx + 1]
        clusters[best_idx] = merged
        del clusters[best_idx + 1]

    return [
        (members, sum(members) / len(members))
        for members in clusters
    ]
```

- [ ] **Step 4: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_clustering.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/shared/clustering.py packages/server/tests/test_key_levels/test_clustering.py
git commit -m "feat: add agglomerative clustering utility for key levels"
```

---

### Task 7: KeyLevelDetector protocol

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/detector.py`

- [ ] **Step 1: Write detector.py**

Create `packages/server/server/store/indicators/key_levels/detector.py`:

```python
"""KeyLevelDetector protocol — the contract all detection methods implement."""

from __future__ import annotations

from typing import Protocol

from nautilus_trader.model.data import Bar

from server.store.indicators.key_levels.model import KeyLevel, Source


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
git add packages/server/server/store/indicators/key_levels/detector.py
git commit -m "feat: add KeyLevelDetector protocol"
```

---

### Task 8: KeyLevelIndicator (NautilusTrader integration)

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/indicator.py`
- Create: `packages/server/tests/test_key_levels/test_indicator.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_indicator.py`:

```python
"""Tests for KeyLevelIndicator — NautilusTrader integration."""

import math

import pytest

from server.store.indicators.key_levels.indicator import KeyLevelIndicator
from server.store.indicators.key_levels.model import KeyLevel, SwingClusterMeta
from server.store.indicators.key_levels.shared.bar_factory import (
    make_bar,
    make_bars_from_closes,
)


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
    # nearest_support should be 99.0 (closest below), not 90.0 (strongest below)
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
    levels = [_make_level(110.0, 0.5)]  # Only above current price
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
cd packages/server && python -m pytest tests/test_key_levels/test_indicator.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write KeyLevelIndicator**

Create `packages/server/server/store/indicators/key_levels/indicator.py`:

```python
"""KeyLevelIndicator — NautilusTrader Indicator subclass.

Composes multiple KeyLevelDetectors and exposes dual output paths:
- .levels -> list[KeyLevel] for strategy consumption
- Scalar summary properties for dashboard/registry integration
"""

from __future__ import annotations

import math

from nautilus_trader.indicators.base import Indicator
from nautilus_trader.model.data import Bar

from server.store.indicators.key_levels.detector import KeyLevelDetector
from server.store.indicators.key_levels.model import KeyLevel, Source


class KeyLevelIndicator(Indicator):

    def __init__(self, detectors: list[KeyLevelDetector]) -> None:
        super().__init__([d.name for d in detectors])
        self._detectors = detectors
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
cd packages/server && python -m pytest tests/test_key_levels/test_indicator.py -v
```

Expected: 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/indicator.py packages/server/server/store/indicators/key_levels/detector.py packages/server/tests/test_key_levels/test_indicator.py
git commit -m "feat: add KeyLevelIndicator with dual output paths"
```

---

### Task 9: SwingClusterDetector

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/detectors/__init__.py`
- Create: `packages/server/server/store/indicators/key_levels/detectors/swing_cluster.py`
- Create: `packages/server/tests/test_key_levels/test_swing_cluster.py`

- [ ] **Step 1: Create detectors package**

```bash
cd packages/server && mkdir -p server/store/indicators/key_levels/detectors && touch server/store/indicators/key_levels/detectors/__init__.py
```

- [ ] **Step 2: Write the test**

Create `packages/server/tests/test_key_levels/test_swing_cluster.py`:

```python
"""Tests for SwingClusterDetector."""

import pytest

from server.store.indicators.key_levels.detectors.swing_cluster import (
    SwingClusterDetector,
)
from server.store.indicators.key_levels.model import SwingClusterMeta
from server.store.indicators.key_levels.shared.bar_factory import (
    make_bar,
    _BASE_TS,
    _1H_NS,
)


def _make_swing_bars():
    """Create bars with a clear swing high at 110 and swing low at 90.

    Pattern: rise to 110, drop to 90, rise to 108 (near 110 cluster),
    drop to 92 (near 90 cluster), then stabilize.
    This should create two clusters: one around 110 (resistance) and one around 90 (support).
    """
    # period=2 fractals need 5-bar patterns per swing
    # Swing high pattern: lower, lower-high, HIGH, lower-high, lower
    # Swing low pattern: higher, higher-low, LOW, higher-low, higher
    data = [
        # First swing high at 110
        (100.0, 102.0, 98.0, 101.0, 100.0),   # bar 0
        (101.0, 106.0, 100.0, 105.0, 100.0),   # bar 1
        (105.0, 110.0, 104.0, 108.0, 100.0),   # bar 2 - swing high
        (108.0, 107.0, 100.0, 102.0, 100.0),   # bar 3
        (102.0, 103.0, 95.0, 96.0, 100.0),     # bar 4
        # First swing low at 90
        (96.0, 97.0, 92.0, 93.0, 100.0),       # bar 5
        (93.0, 94.0, 90.0, 91.0, 100.0),       # bar 6 - swing low
        (91.0, 96.0, 91.0, 95.0, 100.0),       # bar 7
        (95.0, 100.0, 94.0, 99.0, 100.0),      # bar 8
        # Second swing high near 110 (cluster)
        (99.0, 104.0, 98.0, 103.0, 100.0),     # bar 9
        (103.0, 109.0, 102.0, 107.0, 100.0),   # bar 10 - swing high
        (107.0, 106.0, 99.0, 101.0, 100.0),    # bar 11
        (101.0, 102.0, 95.0, 97.0, 100.0),     # bar 12
        # Second swing low near 90 (cluster)
        (97.0, 98.0, 93.0, 94.0, 100.0),       # bar 13
        (94.0, 95.0, 91.0, 92.0, 100.0),       # bar 14 - swing low
        (92.0, 97.0, 91.0, 96.0, 100.0),       # bar 15
        (96.0, 100.0, 95.0, 99.0, 100.0),      # bar 16
    ]
    return [
        make_bar(o, h, l, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, l, c, v) in enumerate(data)
    ]


def test_swing_cluster_no_levels_before_warmup():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_swing_cluster_finds_levels():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    assert len(levels) > 0
    # All levels should have valid structure
    for level in levels:
        assert level.source == "swing_cluster"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, SwingClusterMeta)


def test_swing_cluster_strength_increases_with_bounces():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    # Levels with bounce_count > 1 should have higher strength
    multi_bounce = [l for l in levels if l.bounce_count > 1]
    single_bounce = [l for l in levels if l.bounce_count == 1]
    if multi_bounce and single_bounce:
        assert max(l.strength for l in multi_bounce) >= max(l.strength for l in single_bounce)


def test_swing_cluster_deterministic():
    bars = _make_swing_bars()
    det_a = SwingClusterDetector(period=2, cluster_distance=2.0)
    det_b = SwingClusterDetector(period=2, cluster_distance=2.0)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_swing_cluster_reset():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0
    detector.reset()
    assert detector.levels() == []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_swing_cluster.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write SwingClusterDetector**

Create `packages/server/server/store/indicators/key_levels/detectors/swing_cluster.py`:

```python
"""SwingClusterDetector — detect key levels from clustered fractal swing points.

1. Detect fractal swing highs/lows using SwingDetector (Williams fractals).
2. Cluster nearby swings using agglomerative clustering (distance = ATR * cluster_distance).
3. Each cluster becomes a KeyLevel with strength based on bounce count and recency.
"""

from __future__ import annotations

import math

from nautilus_trader.model.data import Bar

from server.store.indicators.key_levels.model import KeyLevel, SwingClusterMeta
from server.store.indicators.key_levels.shared.atr import StreamingAtr
from server.store.indicators.key_levels.shared.clustering import agglomerative_cluster
from server.store.indicators.key_levels.shared.swing import SwingDetector


class SwingClusterDetector:
    """Detects key levels by clustering fractal swing highs and lows.

    Args:
        period: Fractal lookback N (number of bars on each side). Default 2 (5-bar pattern).
        cluster_distance: ATR multiple used as merge threshold for clustering. Default 1.5.
        atr_period: Period for ATR calculation used in clustering distance. Default 14.
        recency_decay: Half-life in bars for recency weighting. Default 100.
        max_swings: Maximum swings to retain in memory. Default 200.
    """

    def __init__(
        self,
        period: int = 2,
        cluster_distance: float = 1.5,
        atr_period: int = 14,
        recency_decay: float = 100.0,
        max_swings: int = 200,
    ) -> None:
        self._period = period
        self._cluster_distance = cluster_distance
        self._recency_decay = recency_decay
        self._max_swings = max_swings

        self._swing_detector = SwingDetector(period=period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0
        self._levels: list[KeyLevel] = []

        # Store swings with their bar index for recency weighting
        self._swing_prices: list[float] = []
        self._swing_indices: list[int] = []
        self._swing_timestamps: list[int] = []
        self._swing_sides: list[str] = []

    @property
    def name(self):
        return "swing_cluster"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._period + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )

        if swing is not None:
            self._swing_prices.append(swing.price)
            self._swing_indices.append(swing.bar_index)
            self._swing_timestamps.append(swing.ts)
            self._swing_sides.append(swing.side)

            # Enforce memory bound
            if len(self._swing_prices) > self._max_swings:
                self._swing_prices.pop(0)
                self._swing_indices.pop(0)
                self._swing_timestamps.pop(0)
                self._swing_sides.pop(0)

        self._bar_index += 1

        # Rebuild levels from clusters
        if self._atr.ready and len(self._swing_prices) >= 1:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        merge_dist = self._atr.value * self._cluster_distance
        if merge_dist <= 0:
            self._levels = []
            return

        clusters = agglomerative_cluster(self._swing_prices, merge_dist)

        # Find which original swing indices belong to each cluster
        # by re-mapping prices to their indices
        price_to_info: dict[int, list[tuple[int, int]]] = {}
        for i, price in enumerate(self._swing_prices):
            price_to_info.setdefault(id(self._swing_prices) + i, []).append(
                (self._swing_indices[i], self._swing_timestamps[i])
            )

        max_bounce = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        swing_idx = 0
        for members, centroid in clusters:
            # Gather info for all swings in this cluster
            cluster_indices: list[int] = []
            latest_ts = 0
            earliest_ts = self._swing_timestamps[-1] if self._swing_timestamps else 0
            for _ in members:
                if swing_idx < len(self._swing_indices):
                    cluster_indices.append(self._swing_indices[swing_idx])
                    ts = self._swing_timestamps[swing_idx]
                    if ts > latest_ts:
                        latest_ts = ts
                    if ts < earliest_ts:
                        earliest_ts = ts
                    swing_idx += 1

            bounce_count = len(members)

            # Recency weight: exponential decay based on how recent the latest touch is
            bars_since = max(0, self._bar_index - max(cluster_indices)) if cluster_indices else 0
            recency_weight = math.exp(-0.693 * bars_since / self._recency_decay)

            # Strength: normalized bounce count * recency
            raw_strength = (bounce_count / max_bounce) * recency_weight
            strength = min(1.0, max(0.0, raw_strength))

            zone_lower = min(members)
            zone_upper = max(members)
            # Ensure zone has some width even for single-bounce levels
            if zone_upper == zone_lower:
                half_atr = self._atr.value * 0.25
                zone_lower -= half_atr
                zone_upper += half_atr

            levels.append(KeyLevel(
                price=centroid,
                strength=strength,
                bounce_count=bounce_count,
                first_seen_ts=earliest_ts,
                last_touched_ts=latest_ts,
                zone_upper=zone_upper,
                zone_lower=zone_lower,
                source="swing_cluster",
                meta=SwingClusterMeta(
                    cluster_radius=merge_dist,
                    pivot_indices=tuple(cluster_indices),
                ),
            ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._levels = []
        self._swing_prices.clear()
        self._swing_indices.clear()
        self._swing_timestamps.clear()
        self._swing_sides.clear()
```

- [ ] **Step 5: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_swing_cluster.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/detectors/ packages/server/tests/test_key_levels/test_swing_cluster.py
git commit -m "feat: add SwingClusterDetector"
```

---

### Task 10: EqualHighsLowsDetector

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/detectors/equal_highs_lows.py`
- Create: `packages/server/tests/test_key_levels/test_equal_highs_lows.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_equal_highs_lows.py`:

```python
"""Tests for EqualHighsLowsDetector."""

import pytest

from server.store.indicators.key_levels.detectors.equal_highs_lows import (
    EqualHighsLowsDetector,
)
from server.store.indicators.key_levels.model import EqualHighsLowsMeta
from server.store.indicators.key_levels.shared.bar_factory import (
    make_bar,
    _BASE_TS,
    _1H_NS,
)


def _make_equal_highs_bars():
    """Bars with 3 swing highs near 110 and 3 swing lows near 90.

    Creates a zigzag: up to ~110, down to ~90, repeated 3 times.
    With period=2 fractals, each peak/trough needs 5 bars.
    """
    data = []
    for cycle in range(3):
        base = cycle * 10  # Offset timestamps
        # Rise to swing high near 110
        data.extend([
            (98.0, 102.0, 97.0, 101.0, 100.0),
            (101.0, 107.0, 100.0, 106.0, 100.0),
            (106.0, 110.0 + cycle * 0.2, 105.0, 108.0, 100.0),  # Swing high: 110.0, 110.2, 110.4
            (108.0, 106.0, 99.0, 100.0, 100.0),
            (100.0, 101.0, 95.0, 96.0, 100.0),
        ])
        # Drop to swing low near 90
        data.extend([
            (96.0, 97.0, 92.0, 93.0, 100.0),
            (93.0, 94.0, 90.0 - cycle * 0.2, 91.0, 100.0),  # Swing low: 90.0, 89.8, 89.6
            (91.0, 96.0, 90.0, 95.0, 100.0),
            (95.0, 100.0, 94.0, 99.0, 100.0),
            (99.0, 101.0, 98.0, 100.0, 100.0),
        ])
    return [
        make_bar(o, h, l, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, l, c, v) in enumerate(data)
    ]


def test_no_levels_before_warmup():
    detector = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, min_touches=2)
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_equal_highs():
    detector = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, min_touches=2)
    bars = _make_equal_highs_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    high_levels = [l for l in levels if isinstance(l.meta, EqualHighsLowsMeta) and l.meta.side == "high"]
    assert len(high_levels) >= 1
    for level in high_levels:
        assert level.source == "equal_highs_lows"
        assert level.price == pytest.approx(110.0, abs=1.0)


def test_finds_equal_lows():
    detector = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, min_touches=2)
    bars = _make_equal_highs_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    low_levels = [l for l in levels if isinstance(l.meta, EqualHighsLowsMeta) and l.meta.side == "low"]
    assert len(low_levels) >= 1
    for level in low_levels:
        assert level.price == pytest.approx(90.0, abs=1.0)


def test_deterministic():
    bars = _make_equal_highs_bars()
    det_a = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, min_touches=2)
    det_b = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, min_touches=2)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, min_touches=2)
    bars = _make_equal_highs_bars()
    for bar in bars:
        detector.update(bar)
    detector.reset()
    assert detector.levels() == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_equal_highs_lows.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write EqualHighsLowsDetector**

Create `packages/server/server/store/indicators/key_levels/detectors/equal_highs_lows.py`:

```python
"""EqualHighsLowsDetector — detect levels where multiple swing highs or lows
touch approximately the same price.

Uses SwingDetector to find fractal pivots, then groups swing highs and swing
lows separately by ATR-based tolerance. Groups with >= min_touches become levels.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from server.store.indicators.key_levels.model import EqualHighsLowsMeta, KeyLevel
from server.store.indicators.key_levels.shared.atr import StreamingAtr
from server.store.indicators.key_levels.shared.clustering import agglomerative_cluster
from server.store.indicators.key_levels.shared.swing import SwingDetector


class EqualHighsLowsDetector:
    """Detects equal highs and equal lows — multiple swing pivots at nearly the same price.

    Args:
        period: Fractal lookback N. Default 2.
        tolerance_atr_multiple: ATR multiple for grouping tolerance. Default 0.5.
        atr_period: ATR calculation period. Default 14.
        min_touches: Minimum equal touches to form a level. Default 2.
        max_swings: Maximum swings to retain per side. Default 100.
    """

    def __init__(
        self,
        period: int = 2,
        tolerance_atr_multiple: float = 0.5,
        atr_period: int = 14,
        min_touches: int = 2,
        max_swings: int = 100,
    ) -> None:
        self._period = period
        self._tolerance_atr_multiple = tolerance_atr_multiple
        self._min_touches = min_touches
        self._max_swings = max_swings

        self._swing_detector = SwingDetector(period=period)
        self._atr = StreamingAtr(period=atr_period)
        self._bar_index: int = 0

        self._swing_high_prices: list[float] = []
        self._swing_high_ts: list[int] = []
        self._swing_low_prices: list[float] = []
        self._swing_low_ts: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self):
        return "equal_highs_lows"

    @property
    def warmup_bars(self) -> int:
        return 2 * self._period + 1

    def update(self, bar: Bar) -> None:
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        swing = self._swing_detector.update(
            high=high, low=low, bar_index=self._bar_index, ts=ts,
        )

        if swing is not None:
            if swing.side == "high":
                self._swing_high_prices.append(swing.price)
                self._swing_high_ts.append(swing.ts)
                if len(self._swing_high_prices) > self._max_swings:
                    self._swing_high_prices.pop(0)
                    self._swing_high_ts.pop(0)
            else:
                self._swing_low_prices.append(swing.price)
                self._swing_low_ts.append(swing.ts)
                if len(self._swing_low_prices) > self._max_swings:
                    self._swing_low_prices.pop(0)
                    self._swing_low_ts.pop(0)

        self._bar_index += 1

        if self._atr.ready:
            self._rebuild_levels()

    def _rebuild_levels(self) -> None:
        tolerance = self._atr.value * self._tolerance_atr_multiple
        if tolerance <= 0:
            self._levels = []
            return

        levels: list[KeyLevel] = []

        # Process highs
        levels.extend(
            self._cluster_side(
                self._swing_high_prices, self._swing_high_ts, "high", tolerance,
            )
        )

        # Process lows
        levels.extend(
            self._cluster_side(
                self._swing_low_prices, self._swing_low_ts, "low", tolerance,
            )
        )

        self._levels = levels

    def _cluster_side(
        self,
        prices: list[float],
        timestamps: list[int],
        side: str,
        tolerance: float,
    ) -> list[KeyLevel]:
        if len(prices) < self._min_touches:
            return []

        clusters = agglomerative_cluster(prices, tolerance)

        # Map prices back to timestamps (prices list and timestamps list are aligned)
        price_ts_pairs = list(zip(prices, timestamps))

        max_touches = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        for members, centroid in clusters:
            if len(members) < self._min_touches:
                continue

            # Find timestamps for these cluster members
            member_ts: list[int] = []
            remaining_pairs = list(price_ts_pairs)
            for member_price in members:
                for idx, (p, t) in enumerate(remaining_pairs):
                    if p == member_price:
                        member_ts.append(t)
                        remaining_pairs.pop(idx)
                        break

            strength = len(members) / max_touches if max_touches > 0 else 0.0

            levels.append(KeyLevel(
                price=centroid,
                strength=min(1.0, strength),
                bounce_count=len(members),
                first_seen_ts=min(member_ts) if member_ts else 0,
                last_touched_ts=max(member_ts) if member_ts else 0,
                zone_upper=max(members),
                zone_lower=min(members),
                source="equal_highs_lows",
                meta=EqualHighsLowsMeta(
                    touch_prices=tuple(members),
                    side=side,
                ),
            ))

        return levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._swing_detector.reset()
        self._atr.reset()
        self._bar_index = 0
        self._levels = []
        self._swing_high_prices.clear()
        self._swing_high_ts.clear()
        self._swing_low_prices.clear()
        self._swing_low_ts.clear()
```

- [ ] **Step 4: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_equal_highs_lows.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/detectors/equal_highs_lows.py packages/server/tests/test_key_levels/test_equal_highs_lows.py
git commit -m "feat: add EqualHighsLowsDetector"
```

---

### Task 11: WickRejectionDetector

**Files:**
- Create: `packages/server/server/store/indicators/key_levels/detectors/wick_rejection.py`
- Create: `packages/server/tests/test_key_levels/test_wick_rejection.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_wick_rejection.py`:

```python
"""Tests for WickRejectionDetector."""

import pytest

from server.store.indicators.key_levels.detectors.wick_rejection import (
    WickRejectionDetector,
)
from server.store.indicators.key_levels.model import WickRejectionMeta
from server.store.indicators.key_levels.shared.bar_factory import (
    make_bar,
    _BASE_TS,
    _1H_NS,
)


def _make_wick_rejection_bars():
    """Bars with long lower wicks near 90 (buy rejection = support)
    and long upper wicks near 110 (sell rejection = resistance).

    A wick rejection bar has a long wick relative to body.
    Lower wick rejection: close near high, long lower shadow.
    Upper wick rejection: close near low, long upper shadow.
    """
    data = []
    # ATR warmup bars (14 normal bars)
    for i in range(14):
        data.append((100.0, 102.0, 98.0, 100.0, 100.0))

    # 3 lower wick rejections near 90 (strong support signal)
    # Pattern: open near 95, drop to ~90, close back near 95 → long lower wick
    data.append((95.0, 96.0, 90.0, 95.5, 100.0))   # wick_ratio ≈ 10 (lower=5, body=0.5)
    data.append((100.0, 102.0, 98.0, 100.0, 100.0))  # normal bar
    data.append((94.0, 95.0, 89.5, 94.5, 100.0))    # wick_ratio ≈ 9
    data.append((100.0, 102.0, 98.0, 100.0, 100.0))  # normal bar
    data.append((96.0, 97.0, 90.5, 96.5, 100.0))    # wick_ratio ≈ 11

    # 3 upper wick rejections near 110 (strong resistance signal)
    data.append((105.0, 110.0, 104.0, 104.5, 100.0))  # long upper wick
    data.append((100.0, 102.0, 98.0, 100.0, 100.0))   # normal
    data.append((106.0, 110.5, 105.0, 105.5, 100.0))  # long upper wick
    data.append((100.0, 102.0, 98.0, 100.0, 100.0))   # normal
    data.append((104.0, 109.5, 103.0, 103.5, 100.0))  # long upper wick

    return [
        make_bar(o, h, l, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, l, c, v) in enumerate(data)
    ]


def test_no_levels_before_atr_ready():
    detector = WickRejectionDetector(min_wick_ratio=2.0, zone_atr_multiple=0.5, min_rejections=2)
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_wick_rejection_zones():
    detector = WickRejectionDetector(
        min_wick_ratio=2.0, zone_atr_multiple=1.5, min_rejections=2, atr_period=14,
    )
    bars = _make_wick_rejection_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    assert len(levels) >= 1
    for level in levels:
        assert level.source == "wick_rejection"
        assert isinstance(level.meta, WickRejectionMeta)
        assert 0.0 <= level.strength <= 1.0


def test_deterministic():
    bars = _make_wick_rejection_bars()
    det_a = WickRejectionDetector(min_wick_ratio=2.0, zone_atr_multiple=1.5, min_rejections=2)
    det_b = WickRejectionDetector(min_wick_ratio=2.0, zone_atr_multiple=1.5, min_rejections=2)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = WickRejectionDetector(min_wick_ratio=2.0, zone_atr_multiple=1.5, min_rejections=2)
    bars = _make_wick_rejection_bars()
    for bar in bars:
        detector.update(bar)
    detector.reset()
    assert detector.levels() == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_wick_rejection.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write WickRejectionDetector**

Create `packages/server/server/store/indicators/key_levels/detectors/wick_rejection.py`:

```python
"""WickRejectionDetector — detect key levels from clustered long-wick bars.

A long wick indicates price rejection at a level. Multiple rejections in the
same price zone form a key level.

Lower wick rejection (support): close > open, lower wick > min_wick_ratio * body.
Upper wick rejection (resistance): close < open, upper wick > min_wick_ratio * body.
For doji bars (body ≈ 0), both wicks are evaluated against absolute thresholds.
"""

from __future__ import annotations

from nautilus_trader.model.data import Bar

from server.store.indicators.key_levels.model import KeyLevel, WickRejectionMeta
from server.store.indicators.key_levels.shared.atr import StreamingAtr
from server.store.indicators.key_levels.shared.clustering import agglomerative_cluster


class WickRejectionDetector:
    """Detects key levels from clustered wick rejection zones.

    Args:
        min_wick_ratio: Minimum wick-to-body ratio to qualify as a rejection. Default 2.0.
        zone_atr_multiple: ATR multiple for grouping rejections into zones. Default 1.0.
        atr_period: ATR calculation period. Default 14.
        min_rejections: Minimum rejections in a zone to form a level. Default 2.
        max_rejections: Maximum rejection events to retain. Default 200.
    """

    def __init__(
        self,
        min_wick_ratio: float = 2.0,
        zone_atr_multiple: float = 1.0,
        atr_period: int = 14,
        min_rejections: int = 2,
        max_rejections: int = 200,
    ) -> None:
        self._min_wick_ratio = min_wick_ratio
        self._zone_atr_multiple = zone_atr_multiple
        self._min_rejections = min_rejections
        self._max_rejections = max_rejections

        self._atr = StreamingAtr(period=atr_period)

        # Store rejection tip prices, wick ratios, and timestamps
        self._rejection_prices: list[float] = []
        self._rejection_ratios: list[float] = []
        self._rejection_ts: list[int] = []

        self._levels: list[KeyLevel] = []

    @property
    def name(self):
        return "wick_rejection"

    @property
    def warmup_bars(self) -> int:
        return 1

    def update(self, bar: Bar) -> None:
        open_ = float(bar.open)
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)
        ts = bar.ts_event

        self._atr.update(high, low, close)

        body = abs(close - open_)
        upper_wick = high - max(open_, close)
        lower_wick = min(open_, close) - low

        # Avoid division by zero for doji bars
        min_body = self._atr.value * 0.01 if self._atr.ready else 0.01

        # Check lower wick rejection (support signal)
        if body > min_body and lower_wick / body >= self._min_wick_ratio:
            self._add_rejection(low, lower_wick / body, ts)
        elif body <= min_body and self._atr.ready and lower_wick > self._atr.value * 0.5:
            self._add_rejection(low, lower_wick / max(body, min_body), ts)

        # Check upper wick rejection (resistance signal)
        if body > min_body and upper_wick / body >= self._min_wick_ratio:
            self._add_rejection(high, upper_wick / body, ts)
        elif body <= min_body and self._atr.ready and upper_wick > self._atr.value * 0.5:
            self._add_rejection(high, upper_wick / max(body, min_body), ts)

        if self._atr.ready:
            self._rebuild_levels()

    def _add_rejection(self, price: float, ratio: float, ts: int) -> None:
        self._rejection_prices.append(price)
        self._rejection_ratios.append(ratio)
        self._rejection_ts.append(ts)
        if len(self._rejection_prices) > self._max_rejections:
            self._rejection_prices.pop(0)
            self._rejection_ratios.pop(0)
            self._rejection_ts.pop(0)

    def _rebuild_levels(self) -> None:
        if len(self._rejection_prices) < self._min_rejections:
            self._levels = []
            return

        tolerance = self._atr.value * self._zone_atr_multiple
        if tolerance <= 0:
            self._levels = []
            return

        clusters = agglomerative_cluster(self._rejection_prices, tolerance)

        # Map prices back to ratios and timestamps
        price_info = list(zip(self._rejection_prices, self._rejection_ratios, self._rejection_ts))

        max_count = max((len(members) for members, _ in clusters), default=1)

        levels: list[KeyLevel] = []
        for members, centroid in clusters:
            if len(members) < self._min_rejections:
                continue

            # Find matching ratios and timestamps
            member_ratios: list[float] = []
            member_ts: list[int] = []
            remaining = list(price_info)
            for member_price in members:
                for idx, (p, r, t) in enumerate(remaining):
                    if p == member_price:
                        member_ratios.append(r)
                        member_ts.append(t)
                        remaining.pop(idx)
                        break

            avg_ratio = sum(member_ratios) / len(member_ratios) if member_ratios else 0.0
            # Strength: rejection count * avg wick ratio, normalized
            raw_strength = (len(members) / max_count) * min(1.0, avg_ratio / 5.0)
            strength = min(1.0, max(0.0, raw_strength))

            levels.append(KeyLevel(
                price=centroid,
                strength=strength,
                bounce_count=len(members),
                first_seen_ts=min(member_ts) if member_ts else 0,
                last_touched_ts=max(member_ts) if member_ts else 0,
                zone_upper=max(members),
                zone_lower=min(members),
                source="wick_rejection",
                meta=WickRejectionMeta(
                    rejection_count=len(members),
                    avg_wick_ratio=avg_ratio,
                ),
            ))

        self._levels = levels

    def levels(self) -> list[KeyLevel]:
        return list(self._levels)

    def reset(self) -> None:
        self._atr.reset()
        self._rejection_prices.clear()
        self._rejection_ratios.clear()
        self._rejection_ts.clear()
        self._levels = []
```

- [ ] **Step 4: Run tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_wick_rejection.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/detectors/wick_rejection.py packages/server/tests/test_key_levels/test_wick_rejection.py
git commit -m "feat: add WickRejectionDetector"
```

---

### Task 12: update_bar function and registry integration test

**Files:**
- Modify: `packages/server/server/store/indicators/registry.py`
- Modify: `packages/server/server/store/indicators/__init__.py`
- Create: `packages/server/tests/test_key_levels/test_registry_integration.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_key_levels/test_registry_integration.py`:

```python
"""Integration test: KeyLevelIndicator through the compute_indicator pipeline."""

import pytest

from server.store.indicators.registry import compute_indicator, INDICATOR_REGISTRY
from server.store.indicators.key_levels.shared.bar_factory import make_bars_from_closes


def test_existing_indicators_still_work():
    """Smoke test: existing SMA still works after restructuring."""
    bars = make_bars_from_closes([100.0 + i for i in range(30)])
    result = compute_indicator("SMA_20", bars)
    assert result.id == "SMA_20"
    assert len(result.outputs["value"]) == 30
    # First 19 are None (warmup), then real values
    assert result.outputs["value"][0] is None
    assert result.outputs["value"][19] is not None
```

- [ ] **Step 2: Run test to verify it passes (existing pipeline works after restructure)**

```bash
cd packages/server && python -m pytest tests/test_key_levels/test_registry_integration.py -v
```

Expected: PASS (if Task 1 restructure was correct).

- [ ] **Step 3: Add update_bar to registry.py**

Add to `packages/server/server/store/indicators/registry.py` after the existing update functions (after `update_hl`):

```python
def update_bar(indicator: IndicatorProto, bar: Bar) -> None:
    """Pass the full Bar to indicators that use handle_bar (e.g., KeyLevelIndicator).

    Unlike update_close/update_hlc/update_hl which extract floats and call
    update_raw, this calls handle_bar directly for indicators that need the
    complete Bar object.
    """
    indicator.handle_bar(bar)  # type: ignore[attr-defined]
```

- [ ] **Step 4: Add update_bar to __init__.py re-exports**

Add `update_bar` to the imports and `__all__` in `packages/server/server/store/indicators/__init__.py`.

- [ ] **Step 5: Run all tests**

```bash
cd packages/server && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/server/store/indicators/registry.py packages/server/server/store/indicators/__init__.py packages/server/tests/test_key_levels/test_registry_integration.py
git commit -m "feat: add update_bar function for key levels registry integration"
```

---

### Task 13: Package exports and full integration test

**Files:**
- Modify: `packages/server/server/store/indicators/key_levels/__init__.py`
- Modify: `packages/server/server/store/indicators/key_levels/shared/__init__.py`
- Modify: `packages/server/server/store/indicators/key_levels/detectors/__init__.py`
- Modify: `packages/server/tests/test_key_levels/test_indicator.py` (add end-to-end test)

- [ ] **Step 1: Set up package exports**

Update `packages/server/server/store/indicators/key_levels/shared/__init__.py`:

```python
"""Shared helpers for key level detection."""

from server.store.indicators.key_levels.shared.atr import StreamingAtr
from server.store.indicators.key_levels.shared.clustering import agglomerative_cluster
from server.store.indicators.key_levels.shared.swing import Swing, SwingDetector

__all__ = ["StreamingAtr", "agglomerative_cluster", "Swing", "SwingDetector"]
```

Update `packages/server/server/store/indicators/key_levels/detectors/__init__.py`:

```python
"""Key level detector implementations."""

from server.store.indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from server.store.indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from server.store.indicators.key_levels.detectors.wick_rejection import WickRejectionDetector

__all__ = ["SwingClusterDetector", "EqualHighsLowsDetector", "WickRejectionDetector"]
```

Update `packages/server/server/store/indicators/key_levels/__init__.py`:

```python
"""Key Levels indicator system.

Plugin-based indicator for detecting horizontal price levels (support/resistance)
through multiple independent detection methods.
"""

from server.store.indicators.key_levels.detector import KeyLevelDetector
from server.store.indicators.key_levels.indicator import KeyLevelIndicator
from server.store.indicators.key_levels.model import KeyLevel, Source, SourceMeta

__all__ = ["KeyLevel", "KeyLevelDetector", "KeyLevelIndicator", "Source", "SourceMeta"]
```

- [ ] **Step 2: Add end-to-end integration test with real detectors**

Append to `packages/server/tests/test_key_levels/test_indicator.py`:

```python
# --- End-to-end with real detectors ---

from server.store.indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from server.store.indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from server.store.indicators.key_levels.shared.bar_factory import _BASE_TS, _1H_NS


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

    return [
        make_bar(o, h, l, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, l, c, v) in enumerate(data)
    ]


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

- [ ] **Step 3: Run all key levels tests**

```bash
cd packages/server && python -m pytest tests/test_key_levels/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Run the full test suite**

```bash
cd packages/server && python -m pytest tests/ -v
```

Expected: All tests PASS (including existing metrics test).

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/indicators/key_levels/ packages/server/tests/test_key_levels/
git commit -m "feat: complete Phase 1 key levels — exports and integration test"
```
