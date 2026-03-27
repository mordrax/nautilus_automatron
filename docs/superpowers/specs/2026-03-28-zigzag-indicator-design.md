# ZigZag Indicator Design Spec

## Overview

A ZigZag indicator for the `nautilus-automatron-indicators` package that identifies significant price reversals by filtering out moves below a configurable threshold. Connects confirmed swing highs and lows, ignoring noise.

Lives alongside the Key Levels indicator in `packages/indicators/indicators/zigzag/`.

## Approach

Single `ZigZagIndicator` class subclassing `nautilus_trader.indicators.base.Indicator` (pure Python, not Cython). Supports two threshold modes (percentage-based and ATR-based). In ATR mode, composes an internal `AverageTrueRange` from nautilus_trader.

Uses a frozen dataclass `ZigZagPivot` for confirmed pivot data, following the Key Levels pattern of frozen dataclasses for data types.

## Data Model

```python
@dataclass(frozen=True)
class ZigZagPivot:
    price: float          # The pivot price (high or low)
    timestamp: int        # Nanosecond timestamp (bar.ts_init)
    direction: int        # 1 = swing high, -1 = swing low
    bar_index: int        # Bar count when pivot was confirmed
```

## Constructor

```python
ZigZagIndicator(
    threshold: float,                     # Reversal threshold value (> 0)
    mode: str = "PERCENTAGE",             # "PERCENTAGE" or "ATR"
    atr_period: int = 14,                 # ATR lookback period (ATR mode only)
    threshold_base: str = "PIVOT",        # "PIVOT" or "TENTATIVE"
    max_pivots: int = 10000,              # Max confirmed pivots (0 = unlimited)
)
```

**Threshold semantics:**
- In PERCENTAGE mode, `threshold` is a decimal ratio: `0.05` means 5%.
- In ATR mode, `threshold` is a multiplier: `2.0` means 2x ATR.

**Threshold base (`threshold_base` parameter):**
- `"PIVOT"` (default): Effective threshold computed from last confirmed pivot price.
- `"TENTATIVE"`: Effective threshold computed from current tentative extreme price.

Effective threshold computation:
- PERCENTAGE + PIVOT: `pivot_price * threshold`
- PERCENTAGE + TENTATIVE: `tentative_price * threshold`
- ATR (either base): `_atr.value * threshold`

**Validation (using `PyCondition`):**
- `threshold` must be positive
- `mode` must be `"PERCENTAGE"` or `"ATR"`
- `threshold_base` must be `"PIVOT"` or `"TENTATIVE"`
- `atr_period` must be positive int
- `max_pivots` must be non-negative

**`params` list:** `[threshold, mode, atr_period, threshold_base, max_pivots]` for `__repr__`.

## Class Architecture

Following the "NO classes except Pydantic models" rule in CLAUDE.md with the unavoidable exception of subclassing `Indicator` (required by NautilusTrader's `register_indicator_for_bars`).

- `ZigZagPivot` — frozen dataclass (immutable data, no behavior)
- `ZigZagIndicator(Indicator)` — required subclass for framework integration

## Public Properties

| Property | Type | Description |
|----------|------|-------------|
| `threshold` | `float` | The configured reversal threshold |
| `atr_period` | `int` | ATR period |
| `max_pivots` | `int` | Max retained pivots (0 = unlimited) |
| `direction` | `int` | Current tentative leg direction: `1` (up), `-1` (down), `0` (unset) |
| `changed` | `bool` | `True` on the bar that confirms a new pivot |
| `pivot_price` | `float` | Price of the last confirmed pivot |
| `pivot_timestamp` | `int` | Nanosecond timestamp of the last confirmed pivot |
| `pivot_direction` | `int` | Direction of the last confirmed pivot |
| `tentative_price` | `float` | Price of the current tentative extreme (repaints) |
| `tentative_timestamp` | `int` | Nanosecond timestamp of the current tentative extreme |
| `pivot_count` | `int` | Number of confirmed pivots |
| `pivots` | `list[ZigZagPivot]` | Copy of confirmed pivot history |

Note: Timestamps use nanosecond integers (`bar.ts_init`) following NautilusTrader conventions, not `pd.Timestamp`. This is consistent with the Key Levels `KeyLevel.first_seen_ts` pattern.

## Algorithm

Same algorithm as the original spec (see `nautilus_trader/docs/superpowers/specs/2026-03-28-zigzag-indicator-design.md`). Key points:

### Initialization
- Track running high/low using `_bar_count == 0` for first-bar detection
- In ATR mode, wait for ATR warmup before checking reversals
- When both high-reversal and low-reversal qualify on same bar, pick the larger move
- `_set_initialized(True)` when first pivot is confirmed

### Active Tracking
- UP leg: extend tentative on new high, confirm pivot on threshold reversal down
- DOWN leg: extend tentative on new low, confirm pivot on threshold reversal up
- Both extension and reversal can trigger on same bar (intentional)
- Threshold recomputed based on `threshold_base` parameter

### Pivot Storage
- When `max_pivots > 0`: `deque(maxlen=max_pivots)` — oldest evicted
- When `max_pivots == 0`: unbounded `list` (for finite historical data)

### Confirmed vs. Tentative
- **Confirmed pivots** (`pivot_price`, `pivot_timestamp`, `pivot_direction`): locked-in, never change
- **Tentative extreme** (`tentative_price`, `tentative_timestamp`): repaints as current leg extends

## Handler Methods

```python
def handle_bar(self, bar: Bar) -> None:
    self._update(
        high=float(bar.high),
        low=float(bar.low),
        close=float(bar.close),
        ts_ns=bar.ts_init,
    )
```

Note: Unlike Cython indicators, the pure Python indicator uses `float(bar.high)` not `bar.high.as_double()`. The internal `_update` method contains the core algorithm. No `handle_quote_tick` or `handle_trade_tick` — this indicator is bar-based only, consistent with Key Levels.

## File Layout

| File | Purpose |
|------|---------|
| `packages/indicators/indicators/zigzag/__init__.py` | Public exports |
| `packages/indicators/indicators/zigzag/model.py` | `ZigZagPivot` frozen dataclass |
| `packages/indicators/indicators/zigzag/indicator.py` | `ZigZagIndicator(Indicator)` class |
| `packages/indicators/tests/zigzag/__init__.py` | Test package |
| `packages/indicators/tests/zigzag/test_model.py` | ZigZagPivot tests |
| `packages/indicators/tests/zigzag/test_indicator.py` | Indicator tests |

## Testing Strategy

Uses existing test infrastructure (`tests/helpers/bar_factory.py`, `conftest.py` fixtures).

1. **ZigZagPivot** — immutability, equality
2. **Instantiation** — defaults, name, repr, validation errors
3. **Percentage mode reversals** — up-to-down, down-to-up, extending tentative
4. **Full zigzag sequence** — multiple pivots accumulated
5. **ATR mode** — warmup delay, reversal with dynamic threshold
6. **Threshold base** — PIVOT vs TENTATIVE behavior difference
7. **max_pivots** — oldest evicted when limit reached
8. **Changed flag** — True only on confirmation bar, False on next
9. **Tentative vs confirmed** — tentative repaints, confirmed does not
10. **Timestamp tracking** — distinct timestamps stored correctly
11. **Reset** — all state cleared
12. **Handle bar** — integration with Bar objects via bar_factory

## Relationship to Key Levels

The ZigZag indicator is a sibling to Key Levels in `packages/indicators/`. Both:
- Subclass `nautilus_trader.indicators.base.Indicator`
- Use frozen dataclasses for output data
- Live in their own subdirectory under `indicators/`
- Share test infrastructure (`bar_factory`, `conftest.py`)

ZigZag is simpler — no detector protocol or plugin system needed. It's a single indicator with a single algorithm, parameterized by mode and threshold.
