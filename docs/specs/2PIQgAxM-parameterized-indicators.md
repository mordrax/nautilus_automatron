# Spec: Parameterized indicators with per-indicator config form

**Card:** [#111 — Parameterized indicators with per-indicator config form in dashboard](https://trello.com/c/2PIQgAxM)
**Status:** Draft — pending user approval
**Owner:** automatron orchestrator

## 1. Goal

Allow the user to add an indicator (SMA, EMA, ZigZag, etc.) to a backtest run and configure its parameters via a small per-indicator form, instead of relying on fixed presets (`ZigZag_5pct`, `SMA_20`, ...) baked into the registry. Persist the per-run indicator selection server-side so it survives reload.

Out of scope (tracked elsewhere): Postgres-backed storage (card #129), per-run color persistence, per-run panel layout, indicator math changes.

## 2. Identity model

Each indicator on the chart is an **instance** with a client-generated UUID:

```ts
type IndicatorInstance = {
  id: string                          // UUID — stable across param edits
  type: string                        // "SMA" | "EMA" | "ZigZag" | ...
  params: Record<string, number>      // { period: 20 }
}
```

UUIDs (rather than deterministic `SMA:period=20` ids) because:
- Two instances with identical params are legitimate (e.g. comparing colors).
- Editing params should not change identity — color and any future per-instance state survive a param change. With deterministic ids, every edit would be delete + create.

## 3. Backend registry shape

Replaces `INDICATOR_REGISTRY` keyed by preset id with `INDICATOR_TYPES` keyed by indicator type.

```python
from dataclasses import dataclass
from typing import Any, Callable, Literal

@dataclass(frozen=True)
class ParamSchema:
    name: str
    type: Literal["int", "float"]
    default: int | float
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    label: str | None = None         # display label; defaults to name

@dataclass(frozen=True)
class IndicatorType:
    type: str                        # "SMA"
    label_template: str              # "SMA({period})" — formatted with params
    display: Display                 # "overlay" | "panel"
    outputs: tuple[str, ...]
    params: tuple[ParamSchema, ...]
    factory: Callable[[dict[str, Any]], IndicatorProto]
    update: UpdateFn

INDICATOR_TYPES: dict[str, IndicatorType] = {
    "SMA": IndicatorType(
        type="SMA",
        label_template="SMA({period})",
        display="overlay",
        outputs=("value",),
        params=(ParamSchema(name="period", type="int", default=20, min=2, max=500),),
        factory=lambda p: SimpleMovingAverage(period=p["period"]),
        update=update_single_value,
    ),
    # EMA, BB, RSI, MACD, ATR, Stochastics, ZigZag, Donchian, HMA — same shape
}
```

The old `INDICATOR_REGISTRY` is **removed**, not migrated. There is no on-disk state referencing the old preset ids; `localStorage indicator-colors` keyed by those ids becomes dead and the user re-picks colors. Accepted regression.

## 4. Backend API

| Endpoint | Change | Body / Query | Returns |
|---|---|---|---|
| `GET /api/indicators` | Updated | — | `IndicatorType[]` — id, label_template, display, outputs, param schema |
| `POST /api/bars/{bar_type:path}/indicators` | **Replaces** the existing GET | `{ instances: IndicatorInstance[] }` | `IndicatorResult[]` keyed by instance `id` |
| `GET /api/runs/{run_id}/viewer-state` | New | — | `{ indicators: IndicatorInstance[] }` — empty default if file missing |
| `PUT /api/runs/{run_id}/viewer-state` | New | `{ indicators: IndicatorInstance[] }` | `204 No Content` (atomic write) |

Why POST for the indicators endpoint: query strings can't cleanly carry per-instance param objects, and we're sending a list of structured payloads on every request. The endpoint is idempotent; POST is just for the body shape.

## 5. Sidecar JSON storage (interim)

File: `backtest_catalog/backtest/{run_id}/viewer_state.json`

```json
{ "indicators": [
  { "id": "uuid-1", "type": "SMA",    "params": { "period": 20 } },
  { "id": "uuid-2", "type": "SMA",    "params": { "period": 50 } },
  { "id": "uuid-3", "type": "ZigZag", "params": { "threshold": 0.05 } }
]}
```

Atomic write: write to `viewer_state.json.tmp` then `os.rename`. Card #129 (Postgres) will migrate this into the DB and retire the sidecar.

## 6. Frontend types + hook

```ts
export type ParamSchema = {
  name: string
  type: 'int' | 'float'
  default: number
  min?: number
  max?: number
  step?: number
  label?: string
}

export type IndicatorType = {
  type: string
  labelTemplate: string
  display: 'overlay' | 'panel'
  outputs: readonly string[]
  params: readonly ParamSchema[]
}

export type IndicatorInstance = {
  id: string
  type: string
  params: Record<string, number>
}
```

`useIndicators(runId, barType)` is rewritten:

- On mount, `GET /api/runs/{runId}/viewer-state` loads `instances: IndicatorInstance[]`.
- Mutations (`addInstance`, `editInstance`, `removeInstance`) update local state and **debounce-flush** via `PUT /api/runs/{runId}/viewer-state` (300 ms debounce — covers fast edits without N writes).
- React Query fetches indicator data via `POST .../indicators` with the current `instances` payload; query key is a stable hash of the instances so identical payloads dedupe.

## 7. UI flow

```
┌──────────────────────────────────────────────────┐
│ [SMA(20) ✎ ×] [SMA(50) ✎ ×] [ZigZag(5%) ✎ ×]  + │
└──────────────────────────────────────────────────┘
                                                  ▲
                          click + ⇒ popover:      │
                          ┌───────────────────┐   │
                          │ Pick indicator: ▼ │   │
                          │  SMA              │   │
                          │  EMA              │   │
                          │  ZigZag           │   │
                          └───────────────────┘
                          → after pick, popover swaps to param form:
                          ┌───────────────────┐
                          │ SMA               │
                          │ period: [ 20 ] ▲▼ │
                          │ [ Cancel ] [Add]  │
                          └───────────────────┘
```

- Clicking ✎ on a chip reopens the same form prefilled with that instance's params (Save instead of Add).
- Validation per `ParamSchema` (min/max, int vs float, required); inline error under each field; submit disabled while invalid.
- `IndicatorSelector` → `IndicatorInstanceSelector` (renamed). New sub-components: `IndicatorChip`, `AddIndicatorPopover`, `IndicatorParamForm`.

## 8. Tests

| Layer | Coverage |
|---|---|
| Vitest unit | `IndicatorParamForm` (defaults populated, validation per schema, submit disabled on invalid, edit-mode prefills). Param-schema helpers (`validate`, `coerce`). `useIndicators` add/edit/remove + debounced PUT (single flush after rapid edits) + load-on-mount round-trip (mocked fetch). UUID generator stability. |
| pytest | `viewer-state` GET missing → empty default; PUT then GET round-trips; PUT rejects malformed body (400); 404 if run_id doesn't exist. POST indicators route: accepts instance list, dispatches to correct factory, returns per-instance results. |
| Playwright e2e | One spec, headless: add SMA(20) → chart shows it → edit period to 30 → chart updates → add SMA(50) → both shown → remove SMA(30) → only SMA(50) remains → reload → SMA(50) reappears. |

## 9. Migration

- No data migration. Old preset ids no longer exist anywhere in the code.
- Old `localStorage indicator-colors` keyed by old preset ids becomes dead; new color storage keys by instance UUID (still `localStorage` in this card — per-run server-side color persistence is card #129).
- No existing `viewer_state.json` files in the wild (first card to write them).

## 10. Files touched

```
packages/server/server/store/indicators.py             (rewrite registry)
packages/server/server/routes/indicators.py            (POST body, return shape)
packages/server/server/routes/viewer_state.py          (new)
packages/server/server/main.py                         (register new router)
packages/server/tests/test_indicators_route.py         (new)
packages/server/tests/test_viewer_state_route.py       (new)

packages/client/src/types/api.ts                       (new types)
packages/client/src/hooks/use-indicators.ts            (rewrite)
packages/client/src/hooks/use-indicators.test.ts       (new)
packages/client/src/lib/indicator-params.ts            (new: validate/coerce)
packages/client/src/lib/indicator-params.test.ts       (new)
packages/client/src/components/chart/indicator-selector/
  IndicatorSelector.tsx                                (rewrite → IndicatorInstanceSelector)
  IndicatorChip.tsx                                    (new)
  AddIndicatorPopover.tsx                              (new)
  IndicatorParamForm.tsx                               (new)
  IndicatorParamForm.test.tsx                          (new)
packages/client/src/lib/api.ts                         (POST + viewer-state methods)
packages/client/src/pages/RunDetailPage.tsx            (pass runId to useIndicators)
packages/client/e2e/parameterized-indicators.spec.ts   (new)
```

## 11. Acceptance criteria

- SMA, EMA, ZigZag (and every other indicator) parameterized through the same `IndicatorType` mechanism — no per-indicator special-casing in the UI.
- Adding the same indicator twice with different params produces two independent overlays/panels.
- Old fixed presets (`ZigZag_5pct`, `ZigZag_3pct`, `ZigZag_01pct`, etc.) are gone — no behavioral regression beyond the documented color-reset.
- Indicator selection persists per run: reload → same instances reappear.
- Vitest, pytest, and Playwright coverage from §8 all pass.
- Lint + typecheck clean.
