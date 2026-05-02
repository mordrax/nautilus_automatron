# Key Levels — Event-Based Model Vertical Slice

**Trello:** [#118](https://trello.com/c/x87rBYcx)
**Branch:** `feature/key-levels-event-model-slice`
**Date:** 2026-05-02

## Goal

Vertical slice proving the new event-based `KeyLevel` data model end-to-end with **one detector only** (`equal_highs_lows`). Replace the snapshot-based `KeyLevel` shape with a lifecycle-tracked one, ship a server endpoint, and render horizontals on the candlestick chart.

This validates the architecture before broader migration. Other detectors will be migrated one card per phase as follow-ups.

## Why

The current `KeyLevel` model is a per-bar snapshot: detectors rebuild their level set on every bar. To render horizontals on a chart that span time ranges (start to end), we need lifecycle-tracked levels with `start_ts`/`end_ts`. Per-bar projection (e.g., a `nearest_support` array) would be O(bars) bytes but only ~50–500 actual levels exist — wasteful and lossy.

## Scope

1. Replace `KeyLevel` dataclass in `packages/indicators/indicators/key_levels/model.py`.
2. Rewrite `EqualHighsLowsDetector` to track lifecycle (born / touched / ended).
3. Update `KeyLevelIndicator` to expose new shape via `.levels`.
4. Add server endpoint `GET /api/bars/{bar_type}/key-levels?detectors=equal_highs_lows` and discovery endpoint `GET /api/key-levels/detectors`.
5. Add frontend hook + source-agnostic eCharts markLine segment renderer.
6. Add toggle UI for show/hide.
7. Validate in Chrome on localhost:5173.

## Out of scope

- Migrating any detector other than `equal_highs_lows` (covered by follow-up cards).
- Backwards compatibility for old `KeyLevel` consumers — replacement, not parallel.
- Per-detector style customization beyond a basic source-keyed color map.
- Caching, pagination, date-range filtering on the API.
- Click-to-detail, strength filtering, or other UI features beyond toggle + render.

## Breaking change accepted

Replacing `KeyLevel` will break:

- `wick_rejection` (other Phase 1 detector on main).
- All Phase 2 detectors merged on main (`atr_volatility`, `fibonacci`, `pivot_points`, `psychological`).
- All open PRs #34–37 (Phases 3–6) — already converted to draft.

Each broken detector has a follow-up migration card. PRs #34–37 stay draft until their migration cards land. Until each phase migrates, those detectors will not import and their tests will fail. The slice keeps `equal_highs_lows` working and disables imports of the broken detectors at registry level so the server still starts.

## Design

### Data Model

`packages/indicators/indicators/key_levels/model.py`:

```python
@dataclass(frozen=True)
class KeyLevel:
    price: float                      # the horizontal price
    strength: float                   # 0..1, detector-defined
    start_ts: int                     # ns — when level became valid
    end_ts: int | None                # ns — None = still active at end of data
    source: Source                    # "equal_highs_lows" | "wick_rejection" | ...
    bounce_count: int                 # detector-primary count (swings, for EHL)
    zone_upper: float | None          # for zoned detectors; None for pure horizontals
    zone_lower: float | None
    meta: SourceMeta                  # discriminated union by source
```

Removed: `first_seen_ts`, `last_touched_ts` (subsumed). Added: `start_ts`, `end_ts: int | None`.

`EqualHighsLowsMeta` adds `touch_count: int`:

```python
@dataclass(frozen=True)
class EqualHighsLowsMeta:
    touch_prices: tuple[float, ...]
    side: Literal["high", "low"]
    touch_count: int  # bar high/low entries within tolerance band over level lifetime
```

### EqualHighsLows Detector Lifecycle

Internal state:

```python
@dataclass
class _TrackedLevel:
    id: int
    side: Literal["high", "low"]
    centroid: float                 # running mean of cluster members
    members: list[float]
    member_ts: list[int]
    start_ts: int                   # ts of swing that brought cluster to min_touches
    end_ts: int | None
    bounce_count: int
    touch_count: int
    last_touch_ts: int
    bars_through: int               # consecutive bars closed beyond level (break detection)
```

Detector keeps `self._tracked: list[_TrackedLevel]` (active + finalized in one list, ordered by `start_ts`).

Constructor adds:

```python
EqualHighsLowsDetector(
    period: int = 2,
    tolerance_atr_multiple: float = 0.5,    # existing — cluster + touch band
    atr_period: int = 14,
    min_touches: int = 2,                    # existing — formation threshold
    break_atr_multiple: float = 1.0,         # NEW — close beyond by N×ATR = break candidate
    break_consecutive_bars: int = 2,         # NEW — K consecutive bars to confirm break
    max_idle_bars: int = 200,                # NEW — aged-out threshold
    strength_decay_k: float = 3.0,           # NEW — exponential decay knob
)
```

Per-bar `update(bar)` flow:

1. Update `_atr` and `_swing_detector`.
2. **Bar-level touch** (active levels only): if `bar.low ≤ centroid + tol AND bar.high ≥ centroid − tol`, then `touch_count += 1`, `last_touch_ts = bar.ts_event`.
3. **Break check** (active levels only): per side, if `bar.close` is beyond level by `break_atr_multiple × ATR` (close > centroid + N·ATR for "high" side, close < centroid − N·ATR for "low" side), increment `bars_through`; else reset to 0. If `bars_through ≥ break_consecutive_bars`, set `end_ts = bar.ts_event`.
4. **Aged-out check** (active levels only): if `bar.ts_event − last_touch_ts > max_idle_bars × bar_interval`, set `end_ts = last_touch_ts`. (`bar_interval` is detected as the diff between consecutive bar timestamps and stored on first occurrence.)
5. **Swing handling** (when `_swing_detector` returns a swing this bar):
   - Try to match the swing to an *active* level on the same side within `tolerance × ATR` of `centroid`.
   - If matched: append to `members`, recompute `centroid` (running mean), `bounce_count += 1`, update `last_touch_ts` = swing.ts.
   - If unmatched: stash the swing in a side-specific buffer `_pending_swings[side]: list[(price, ts)]`. After stashing, scan the buffer: any subset of size ≥ `min_touches` with mutual range ≤ `tolerance × ATR` becomes a new `_TrackedLevel` (`start_ts` = ts of the most recent swing in the qualifying subset; the earlier swings count toward `bounce_count`). Promoted swings are removed from the buffer.

`levels()` returns the full catalogue (active + finalized), each as a frozen `KeyLevel`. Strength computed on demand:

```python
strength = exp(-(bounce_count - min_touches) / strength_decay_k)
```

At `bounce_count = 2`: strength = 1.0. At 5: 0.37. At 10: 0.05.

Reset clears `_tracked`, swing buffers, ATR, swing detector, bar index/interval.

Removed: `_rebuild_levels`, `_levels`, `max_swings` cap (replaced by per-level lifecycle).

### Server Endpoint

New files:

- `packages/server/server/routes/key_levels.py`
- `packages/server/server/store/key_levels.py`

Wired into `packages/server/server/main.py` alongside other routes.

DTO (Pydantic) with discriminated meta union:

```python
class EqualHighsLowsMetaDto(BaseModel):
    kind: Literal["equal_highs_lows"] = "equal_highs_lows"
    touch_prices: tuple[float, ...]
    side: Literal["high", "low"]
    touch_count: int

SourceMetaDto = Annotated[Union[EqualHighsLowsMetaDto], Field(discriminator="kind")]

class KeyLevelDto(BaseModel):
    price: float
    strength: float
    start_ts: str                     # ISO 8601
    end_ts: str | None                # ISO 8601 or null
    source: Literal["equal_highs_lows"]
    bounce_count: int
    zone_upper: float | None
    zone_lower: float | None
    meta: SourceMetaDto
```

Detector registry:

```python
DETECTOR_REGISTRY: dict[str, Callable[[], DetectorProto]] = {
    "equal_highs_lows": lambda: EqualHighsLowsDetector(),
}

DETECTOR_META = [
    {"id": "equal_highs_lows", "label": "Equal Highs/Lows", "color": "#5470c6"},
]
```

Endpoints:

```
GET /api/bars/{bar_type:path}/key-levels?detectors=equal_highs_lows
  → list[KeyLevelDto]
  404 if no bars; 400 if unknown detector

GET /api/key-levels/detectors
  → list of {id, label, color} for the detector picker UI
```

Compute path:

```python
def compute_key_levels(detector_id, bars) -> list[KeyLevelDto]:
    detector = DETECTOR_REGISTRY[detector_id]()
    for bar in bars:
        detector.update(bar)
    return [_to_dto(lvl) for lvl in detector.levels()]
```

### Frontend

New files:

- `packages/client/src/types/key-levels.ts` — TypeScript types matching the Pydantic DTO.
- `packages/client/src/lib/key-levels-api.ts` — fetch wrapper.
- `packages/client/src/hooks/use-key-levels.ts` — React Query hook (mirrors `use-indicators.ts`).
- `packages/client/src/lib/key-level-render.ts` — pure builder: `(KeyLevelDto[], datetimeLabels) → eCharts series`.
- `packages/client/src/components/chart/KeyLevelsPanel.tsx` — toggle UI.

Modified:

- `packages/client/src/components/chart/CandlestickChart.tsx` — accept `keyLevels?: readonly KeyLevelDto[]` prop, attach a transparent line series carrying markLine segment data.
- The page that renders the chart (run detail page) — add `KeyLevelsPanel`, manage `selectedDetectors` state, pass through to chart.

Renderer key detail: x-axis is `type: 'category'` with ISO datetime strings as labels. eCharts `coord: [x, y]` on a category axis must reference an existing label value. `snapToCategory(ts, labels)` does a binary search over labels to find the closest one — handles levels whose start/end timestamps fall between bars. Levels with `end_ts == null` extend to the last label.

Strength → opacity (0.25 + 0.65 × strength) and width (baseWidth + 2 × strength). Source color comes from `SOURCE_STYLE[source]` map.

Toggle UI for the slice = one checkbox `[x] Equal Highs/Lows`. State lives in the parent rendering the chart; passed down as `selectedDetectors: readonly string[]`.

## Acceptance Criteria

- New `KeyLevel` shape committed; old shape removed.
- `EqualHighsLowsDetector` emits lifecycle-tracked levels; existing tests updated to verify lifecycle (start_ts, end_ts, bounce_count over time, decay strength).
- API returns event-based payload, no per-bar arrays.
- Chart renders horizontals at correct prices over correct time ranges.
- Strength visually mapped to opacity/width.
- Playwright e2e: toggle works, levels appear in chart series, opacity correlates with strength.
- Lint + typecheck pass.
- Chrome validation passes on localhost:5173 with real backtest data.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Other detectors break compilation | Disable their imports in registry; tests that exercise them are skipped/removed for slice, restored when migration cards land. |
| `KeyLevelIndicator` consumed by other code | Search for callers; only `equal_highs_lows` is currently wired to it. Adjust callers in this slice. |
| Snap-to-category edge cases | Use binary search; test bound conditions (ts before first label, after last label). |
| Chart series collision with trade markLine | Use a separate transparent line series; do not mutate candlestick markLine. |

## Follow-ups (not this slice)

- #119 — wick_rejection migration
- #120 — Phase 2 (atr_volatility, fibonacci, pivot_points, psychological) migration
- #121–#124 — Phase 3–6 migrations (each blocked on its PR merging first)
- Future: zoned detector rendering (markArea), per-level detail panel, strength filtering, color customization.
