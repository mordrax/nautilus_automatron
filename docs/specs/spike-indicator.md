# Spike Indicator — Design Spec

Trello card: [TlZ2p91C — Spike Indicator](https://trello.com/c/TlZ2p91C)

## Goal

Detect a sharp directional price move over a short window, optionally confirmed by abnormal volume.

## Rules

A spike is confirmed when both apply:

1. **Price (always)** — the absolute price move across a short *measurement window* of N bars exceeds a threshold relative to the typical move across the preceding *baseline window* of M bars.
2. **Volume (conditional)** — when bars carry usable volume, the measurement-window volume must also exceed a threshold relative to baseline-window volume. If volume data is absent, only the price rule applies.

"Usable volume" = volumes observed during warmup are non-zero and not all identical (i.e. not a synthetic/placeholder feed). This is determined once after warmup and fixed for the run; no mid-run switching.

"Typical" is computed via one of: arithmetic mean, [median](https://en.wikipedia.org/wiki/Median), or [z-score](https://en.wikipedia.org/wiki/Standard_score).

## Move methods

The user picks how the "recent move" is measured. All three are exposed via a `move_method` parameter on a single indicator.

### `NET` — directional close-to-close

```
move      = close[-1] - close[-N-1]
magnitude = |move|
direction = sign(move)
```

Captures net displacement. Misses moves that round-trip within the window.

### `EXCURSION` — max signed excursion

```
prior_close   = close[-N-1]
up_excursion  = max(high[-N:]) - prior_close
down_excursion = prior_close - min(low[-N:])

if up_excursion >= down_excursion:
    magnitude = up_excursion;   direction = +1
else:
    magnitude = down_excursion; direction = -1
```

Captures intra-window spikes that round-trip. Default.

### `RANGE` — high-low range, signed by net

```
magnitude = max(high[-N:]) - min(low[-N:])
direction = sign(close[-1] - close[-N-1])
```

Largest possible magnitude. Conflates whippy bars with directional spikes.

## Algorithm (per bar)

```
on_bar(bar):
  1. update rolling buffers: closes, highs, lows, volumes (size = baseline_window + measurement_window + 1)
  2. if buffer not yet full: increment warmup counter, return
  3. on the bar that first fills the buffer:
       - inspect volumes during warmup → set volume_mode
         (PRICE_AND_VOLUME if non-zero and not all identical, else PRICE_ONLY;
          require_volume override may force ALWAYS or NEVER)
       - mark indicator initialized
  4. if cooldown counter > 0: decrement, return
  5. compute recent_move via move_method (NET / EXCURSION / RANGE) → (magnitude, direction)
  6. build baseline distribution: for each of the M-N+1 overlapping N-bar windows
     in the preceding baseline_window bars, compute the same |move|.
  7. evaluate price rule:
       - MEAN   :  magnitude ≥ mean(baseline)   * price_threshold
       - MEDIAN :  magnitude ≥ median(baseline) * price_threshold
       - ZSCORE :  (magnitude - mean(baseline)) / stdev(baseline) ≥ price_threshold
  8. if volume_mode == PRICE_AND_VOLUME:
       - recent_volume   = sum(volume[-N:])
       - baseline_volume = same overlapping sums over preceding M bars
       - evaluate volume rule with same statistic family
  9. if price rule passes AND (volume_mode == PRICE_ONLY OR volume rule passes):
       - emit Spike record
       - set cooldown counter = cooldown_bars
       - update live attributes (changed, direction, current_spike, spike_count)
```

## Baseline distribution mechanics

**Sampling.** At each bar after warmup the baseline is `M - N + 1` overlapping N-bar moves taken over the preceding `baseline_window` bars.

Example with `baseline_window=20`, `measurement_window=5`:

- baseline sample 1 → move over bars `[t-25, t-20]`
- baseline sample 2 → move over bars `[t-24, t-19]`
- …
- baseline sample 16 → move over bars `[t-10, t-5]`

That gives 16 samples per bar. Computed incrementally — new sample added each bar, oldest dropped.

**Warmup length.** `baseline_window + measurement_window` bars. The indicator becomes `initialized` once it has seen that many bars and the first baseline can be computed alongside the first recent move.

## Parameters

| Param | Type | Default | Notes |
|---|---|---|---|
| `move_method` | `MoveMethod` enum | `EXCURSION` | `NET` / `EXCURSION` / `RANGE` |
| `statistic` | `Statistic` enum | `ZSCORE` | `MEAN` / `MEDIAN` / `ZSCORE` |
| `measurement_window` | int | 5 | N |
| `baseline_window` | int | 20 | M (must be ≥ measurement_window + 1) |
| `price_threshold` | float | 2.5 | Single default across all statistics; user adjusts when switching statistic |
| `volume_threshold` | float | 2.0 | Single default across all statistics |
| `cooldown_bars` | int | 20 | 0 disables cooldown. Independent of `baseline_window` |
| `require_volume` | `VolumeMode` enum | `AUTO` | `AUTO` / `ALWAYS` / `NEVER` |
| `max_spikes` | int | 10000 | 0 = unlimited |

All parameters are surfaced to the indicator-selector form. Defaults are static — no constructor-time substitution. Users adjust thresholds explicitly when switching between MEAN / MEDIAN / ZSCORE statistics, because each statistic uses a different scale (multiplier vs sigma-count).

## Volume-mode latching

Set once at the end of warmup, then never changes for the run.

- `require_volume = AUTO` (default): inspect warmup volumes; if non-zero and not all identical, latch to `PRICE_AND_VOLUME`, else `PRICE_ONLY`.
- `require_volume = ALWAYS`: latch to `PRICE_AND_VOLUME` regardless. Volume rule is enforced even if all-zero, which means the indicator will never fire in that case (acceptable — caller asked for it).
- `require_volume = NEVER`: latch to `PRICE_ONLY` regardless.

## Output

```python
class MoveMethod(Enum):
    NET = "NET"
    EXCURSION = "EXCURSION"
    RANGE = "RANGE"

class Statistic(Enum):
    MEAN = "MEAN"
    MEDIAN = "MEDIAN"
    ZSCORE = "ZSCORE"

class VolumeMode(Enum):
    AUTO = "AUTO"          # only valid as input; latched to PRICE_AND_VOLUME or PRICE_ONLY
    ALWAYS = "ALWAYS"      # input only
    NEVER = "NEVER"        # input only
    PRICE_AND_VOLUME = "PRICE_AND_VOLUME"  # latched runtime state
    PRICE_ONLY = "PRICE_ONLY"              # latched runtime state

@dataclass(frozen=True)
class Spike:
    direction: int                # +1 (up) or -1 (down)
    magnitude: float              # the |move| that fired
    price_at_fire: float          # close[-1] at the firing bar
    start_ts: int                 # bar.ts_init of the first bar of the measurement window
    end_ts: int                   # bar.ts_init of the firing bar
    start_bar_index: int
    end_bar_index: int
    volume_ratio: float | None    # recent_volume / baseline_centre; None in PRICE_ONLY mode
    move_method: MoveMethod
    statistic: Statistic
```

### Live attributes (match ZigZag conventions)

- `volume_mode: VolumeMode` — read-only; one of `PRICE_AND_VOLUME` / `PRICE_ONLY` after warmup
- `direction: int` — direction of most recent confirmed spike, 0 before any fire
- `changed: bool` — `True` only on the bar a spike fires
- `current_spike: Spike | None` — last confirmed spike
- `spike_count: int`
- `spikes` property → `list[Spike]` (capped by `max_spikes`)

## Package layout

```
packages/indicators/indicators/spike/
├── __init__.py
├── indicator.py    ← SpikeIndicator(Indicator)
├── moves.py        ← three pure move functions
└── model.py        ← Spike dataclass + MoveMethod / Statistic / VolumeMode enums
```

Tests at `packages/indicators/tests/test_spike.py`, parametrized over `move_method` so all three paths are exercised per scenario.

## Framework extension: enum parameters

The existing parameterized-indicator framework (`packages/server/server/store/indicators.py`, `packages/client/src/components/chart/indicator-selector/IndicatorParamForm.tsx`) supports only numeric `int` / `float` parameters. The spike indicator requires three enum parameters (`move_method`, `statistic`, `require_volume`), so the framework is extended in this PR:

**Backend (`packages/server/server/store/indicators.py`):**
- `ParamSchema.type` gains `"enum"` in its `Literal` union.
- New optional field `choices: tuple[str, ...] | None = None`; required when `type == "enum"`.
- `ParamSchema.default` widens to `int | float | str`.
- Validation rejects enum values not in `choices`.

**Frontend (`packages/client/src/components/chart/indicator-selector/IndicatorParamForm.tsx`, `packages/client/src/lib/indicator-params.ts`, `packages/client/src/types/api.ts`):**
- Param schema TS type gains `'enum'` variant with `choices: readonly string[]`.
- `coerceParams` passes string enum values through unchanged.
- `validateParams` checks enum membership.
- The form renders a shadcn `<Select>` for enum-typed params (numeric params still render as `<Input>`).

## Backend registration

The indicator registers in `INDICATOR_TYPES` as `"Spike"` with all 9 params exposed. The `factory` lambda maps the schema params (strings for enums) into `SpikeIndicator` constructor arguments. The compute path uses a dedicated `_compute_spike` helper that produces sparse arrays for the chart (`spike_up`, `spike_down`) so the firing bars can be marked, mirroring how `_compute_zigzag` produces a sparse `zigzag` series.

## Chart rendering

The chart (`packages/client/src/components/chart/CandlestickChart.tsx`) reads the `IndicatorResult` for any "Spike" instance and renders the spike events using existing eCharts scatter/marker primitives — no per-indicator frontend module is needed. Up-spikes render at the firing-bar high, down-spikes at the firing-bar low, color from the per-instance color picker, tooltip shows magnitude (and volume ratio when available).

## Tests

Unit tests in `packages/indicators/tests/test_spike.py`, parametrized over `move_method` and `statistic` where relevant:

- No-spike baseline (flat series)
- Up-spike with volume
- Down-spike with volume
- Price rule passes but volume rule blocks (no fire)
- Volume rule passes but price rule blocks (no fire)
- Price-only spike when volume absent (mode latches to `PRICE_ONLY`)
- `require_volume=ALWAYS` with absent volume → never fires
- `require_volume=NEVER` with present volume → fires on price alone
- Warmup boundary (no fire before `M+N` bars seen)
- Cooldown: spike at bar t, no second spike before bar `t + cooldown_bars`
- Reset behaviour: state cleared, buffers empty, mode unset
- Parameter validation: invalid enums, non-positive windows, `baseline_window < measurement_window`, negative thresholds
- Per-statistic threshold defaults applied when not explicit

## Out of scope

- Adaptive / ML-tuned thresholds
- Multi-bar pattern recognition beyond the windows above
- Trade signals or strategy hooks (separate card)
- Tick-level resolution (bars only)
- Persisting spikes to catalog
- Mid-run volume-mode switching

## References

- Closest existing indicator: `packages/indicators/indicators/zigzag/`
- Nautilus indicator base: `nautilus_trader.indicators.base.Indicator`
- Nautilus [`Bar`](https://nautilustrader.io/docs/latest/api_reference/model/data#bar)
- Python [frozen dataclass](https://docs.python.org/3/library/dataclasses.html#frozen-instances)
