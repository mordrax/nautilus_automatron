# Chip Data Source Tooltip — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On `RunDetailPage`, render each `bar_type` chip with a hover/click-pinned tooltip showing on-disk parquet directory, venue, date range, and bar count — sourced from a small extension of `/api/catalog`.

**Architecture:** Server adds three fields (`venue`, `path`, `file_count`) to existing `/api/catalog` entries. Client wraps the existing `<Badge>` chip in a Radix `Tooltip`, looks up its entry by `bar_type` from the cached catalog query, and renders a compact metadata grid with click-to-pin.

**Tech Stack:** Python + FastAPI + Nautilus `ParquetDataCatalog` (server); React + TypeScript + TanStack Query + Radix UI Tooltip + Effect-TS (client); Playwright (e2e).

**Spec:** `docs/superpowers/specs/2026-05-11-chip-data-source-tooltip-design.md`

---

## Task 1: Extend `/api/catalog` response with `venue`, `path`, `file_count`

**Files:**
- Modify: `packages/server/server/store/reader.py:28-69` (`list_catalog_entries`)
- Modify: `packages/server/server/store/transforms.py:220-229` (`catalog_entry_to_dict`)
- Test: `packages/server/tests/test_catalog_route.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_catalog_route.py`:

```python
"""Tests for the /api/catalog route — provenance fields (venue, path, file_count)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.main import create_app


_BAR_TYPE_STR = "TEST.SIM-1-MINUTE-BID-EXTERNAL"


def _make_bar(ts_ns: int) -> Bar:
    return Bar(
        bar_type=BarType.from_str(_BAR_TYPE_STR),
        open=Price.from_str("1.00000"),
        high=Price.from_str("1.00010"),
        low=Price.from_str("0.99990"),
        close=Price.from_str("1.00005"),
        volume=Quantity.from_str("100.00"),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


@pytest.fixture
def store_with_bars(tmp_path: Path) -> Path:
    """Build a real on-disk catalog with one bar_type so the reader can scan it."""
    catalog = ParquetDataCatalog(path=str(tmp_path))
    catalog.write_data([
        _make_bar(1_704_067_200_000_000_000),  # 2024-01-01
        _make_bar(1_704_067_260_000_000_000),  # +60s
    ])
    return tmp_path


def test_catalog_route_includes_venue_path_file_count(
    store_with_bars: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("NAUTILUS_STORE_PATH", str(store_with_bars))
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    entry = body[0]

    assert entry["bar_type"] == _BAR_TYPE_STR
    assert entry["venue"] == "SIM"
    assert entry["path"].endswith("/data/bar/" + _BAR_TYPE_STR)
    assert entry["file_count"] >= 1


def test_catalog_entry_to_dict_venue_null_when_no_dot():
    """venue is null for a malformed bar_type with no '.' separator."""
    from server.store.transforms import catalog_entry_to_dict

    raw = {
        "instrument_id": "NODOTHERE",
        "bar_type": "NODOTHERE-1-MINUTE-BID-EXTERNAL",
        "bar_count": 1,
        "ts_min": 1_704_067_200_000_000_000,
        "ts_max": 1_704_067_200_000_000_000,
        "path": "/tmp/whatever",
        "file_count": 1,
    }
    out = catalog_entry_to_dict(raw)
    assert out["venue"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/server && .venv/bin/pytest tests/test_catalog_route.py -v
```

Expected: both tests FAIL — `KeyError: 'venue'` or `assert ... in response` (fields not yet emitted).

- [ ] **Step 3: Modify `list_catalog_entries` to capture `path` and `file_count`**

In `packages/server/server/store/reader.py`, replace the `entries.append({...})` block (lines 61-67) so each entry includes the bar_type directory path and parquet file count:

```python
        entries.append({
            "instrument_id": instrument_id,
            "bar_type": bar_type_name,
            "bar_count": len(bars),
            "ts_min": ts_min,
            "ts_max": ts_max,
            "path": str(bar_type_dir.resolve()),
            "file_count": sum(1 for _ in bar_type_dir.glob("*.parquet")),
        })
```

- [ ] **Step 4: Modify `catalog_entry_to_dict` to emit `venue`, `path`, `file_count`**

In `packages/server/server/store/transforms.py`, add a helper above `catalog_entry_to_dict` and extend the return dict:

```python
def _parse_venue(bar_type: str) -> str | None:
    """Extract the venue token from a bar_type string.

    Bar types are formatted '{symbol}.{venue}-{aggregation}-{price}-{source}'.
    Returns the venue token (e.g. 'IBCFD', 'SIM') or None if no '.' is present.
    """
    if "." not in bar_type:
        return None
    after_dot = bar_type.split(".", 1)[1]
    return after_dot.split("-", 1)[0] if "-" in after_dot else after_dot


def catalog_entry_to_dict(entry: dict) -> dict:
    """Convert a raw catalog entry from the reader into an API-ready dict."""
    return {
        "instrument": entry["instrument_id"],
        "bar_type": entry["bar_type"],
        "bar_count": entry["bar_count"],
        "start_date": _ns_to_iso(entry["ts_min"]),
        "end_date": _ns_to_iso(entry["ts_max"]),
        "timeframe": _parse_timeframe(entry["bar_type"], entry["instrument_id"]),
        "venue": _parse_venue(entry["bar_type"]),
        "path": entry["path"],
        "file_count": entry["file_count"],
    }
```

Remove the existing `_parse_timeframe`-only `catalog_entry_to_dict` body — replace it wholesale with the version above.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd packages/server && .venv/bin/pytest tests/test_catalog_route.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Run the full server test suite (regression check)**

```bash
cd packages/server && .venv/bin/pytest tests/ -q
```

Expected: no regressions (existing tests still pass).

- [ ] **Step 7: Commit**

```bash
git add packages/server/server/store/reader.py packages/server/server/store/transforms.py packages/server/tests/test_catalog_route.py
git commit -m "feat(catalog): add venue, path, file_count to /api/catalog entries"
```

---

## Task 2: Extend client `CatalogEntry` type

**Files:**
- Modify: `packages/client/src/types/api.ts:118-125`

- [ ] **Step 1: Add the three new fields to the type**

Edit `packages/client/src/types/api.ts` lines 118-125 to read:

```typescript
export type CatalogEntry = {
  readonly instrument: string
  readonly bar_type: string
  readonly bar_count: number
  readonly start_date: string
  readonly end_date: string
  readonly timeframe: string
  readonly venue: string | null
  readonly path: string
  readonly file_count: number
}
```

- [ ] **Step 2: Verify typecheck still passes**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: no errors (no existing code consumes these fields yet).

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/types/api.ts
git commit -m "feat(client): extend CatalogEntry type with venue, path, file_count"
```

---

## Task 3: Create `CatalogTooltipContent` component

**Files:**
- Create: `packages/client/src/components/CatalogTooltipContent.tsx`

- [ ] **Step 1: Write the component**

Create `packages/client/src/components/CatalogTooltipContent.tsx`:

```tsx
import { Copy } from 'lucide-react'
import type { CatalogEntry } from '@/types/api'

type Props = {
  readonly barType: string
  readonly entry: CatalogEntry | undefined
}

const fmtDate = (iso: string): string => iso.slice(0, 10)
const fmtCount = (n: number): string => n.toLocaleString()

const onCopyPath = (path: string) => {
  navigator.clipboard?.writeText(path).catch(() => {
    /* clipboard may be unavailable in insecure contexts; ignore */
  })
}

export const CatalogTooltipContent = ({ barType, entry }: Props) => {
  if (!entry) {
    return (
      <div className="space-y-1">
        <div className="font-semibold">Not in catalog</div>
        <div className="font-mono text-[10px] opacity-80">{barType}</div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
      <span className="opacity-70">Symbol</span>
      <span className="font-mono">{entry.instrument}</span>

      {entry.venue && (
        <>
          <span className="opacity-70">Venue</span>
          <span className="font-mono">{entry.venue}</span>
        </>
      )}

      <span className="opacity-70">Timeframe</span>
      <span className="font-mono">{entry.timeframe}</span>

      <span className="opacity-70">Range</span>
      <span className="font-mono">
        {fmtDate(entry.start_date)} → {fmtDate(entry.end_date)}
      </span>

      <span className="opacity-70">Bars</span>
      <span className="font-mono">{fmtCount(entry.bar_count)}</span>

      <span className="opacity-70">Path</span>
      <span className="font-mono break-all flex items-center gap-1.5">
        <span>{entry.path}</span>
        <button
          type="button"
          aria-label="Copy path"
          onClick={(e) => {
            e.stopPropagation()
            onCopyPath(entry.path)
          }}
          className="opacity-70 hover:opacity-100 shrink-0"
        >
          <Copy className="size-3" />
        </button>
        <span className="opacity-60 shrink-0">({entry.file_count} {entry.file_count === 1 ? 'file' : 'files'})</span>
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/CatalogTooltipContent.tsx
git commit -m "feat(client): add CatalogTooltipContent component"
```

---

## Task 4: Create `BarTypeChip` component with hover + click-to-pin

**Files:**
- Create: `packages/client/src/components/BarTypeChip.tsx`

- [ ] **Step 1: Write the component**

Create `packages/client/src/components/BarTypeChip.tsx`:

```tsx
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { CatalogTooltipContent } from '@/components/CatalogTooltipContent'
import type { CatalogEntry } from '@/types/api'

type Props = {
  readonly barType: string
  readonly entry: CatalogEntry | undefined
}

export const BarTypeChip = ({ barType, entry }: Props) => {
  const [pinned, setPinned] = useState(false)
  const [hovered, setHovered] = useState(false)
  const open = pinned || hovered

  return (
    <Tooltip open={open} onOpenChange={setHovered}>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className="cursor-pointer select-none"
          onClick={() => setPinned((p) => !p)}
          aria-pressed={pinned}
          data-pinned={pinned || undefined}
          data-bartype={barType}
        >
          {barType}
        </Badge>
      </TooltipTrigger>
      <TooltipContent
        className="max-w-[640px] bg-popover text-popover-foreground border border-border shadow-md"
        side="bottom"
        align="start"
        onPointerDownOutside={() => setPinned(false)}
      >
        <CatalogTooltipContent barType={barType} entry={entry} />
      </TooltipContent>
    </Tooltip>
  )
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/BarTypeChip.tsx
git commit -m "feat(client): add BarTypeChip with hover + click-to-pin tooltip"
```

---

## Task 5: Wire `BarTypeChip` into `RunDetailPage`

**Files:**
- Modify: `packages/client/src/pages/RunDetailPage.tsx:5,76-78` (Badge import + chip render)
- Modify: `packages/client/src/pages/RunDetailPage.tsx:28-33` (add `useCatalog` call + map)

- [ ] **Step 1: Add `useCatalog` import + call and `catalogMap`**

At the top of `packages/client/src/pages/RunDetailPage.tsx`:

Add the import after the existing `useKeyLevels` import (around line 23):

```typescript
import { useCatalog } from '@/hooks/use-catalog'
import { BarTypeChip } from '@/components/BarTypeChip'
```

Inside `RunDetailPage`, after `const { data: equity } = useEquity(runId)` (around line 33), add:

```typescript
  const { data: catalog } = useCatalog()
  const catalogMap = Object.fromEntries(
    (catalog ?? []).map((e) => [e.bar_type, e]),
  )
```

- [ ] **Step 2: Replace the `bar_types.map(...)` Badge with `BarTypeChip`**

Change lines 76-78 from:

```tsx
        {runDetail.bar_types.map((bt) => (
          <Badge key={bt} variant="outline">{bt}</Badge>
        ))}
```

to:

```tsx
        {runDetail.bar_types.map((bt) => (
          <BarTypeChip key={bt} barType={bt} entry={catalogMap[bt]} />
        ))}
```

- [ ] **Step 3: Verify typecheck**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/client/src/pages/RunDetailPage.tsx
git commit -m "feat(client): wire BarTypeChip + useCatalog into RunDetailPage"
```

---

## Task 6: Playwright e2e test for the tooltip

**Files:**
- Create: `packages/client/e2e/run-detail-tooltip.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `packages/client/e2e/run-detail-tooltip.spec.ts`:

```typescript
import { test, expect } from '@playwright/test'

test.describe('Run Detail — bar_type chip tooltip', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for the trade navigator to confirm the page is hydrated
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('hovering a chip reveals catalog metadata', async ({ page }) => {
    const chip = page.locator('[data-bartype]').first()
    await expect(chip).toBeVisible()
    await chip.hover()

    const tooltip = page.locator('[data-slot="tooltip-content"]').first()
    await expect(tooltip).toBeVisible()

    // The tooltip shows real provenance, not placeholders
    await expect(tooltip).toContainText(/Symbol/)
    await expect(tooltip).toContainText(/Range/)
    await expect(tooltip).toContainText(/Bars/)
    await expect(tooltip).toContainText(/Path/)
    // Real on-disk path lives under backtest_catalog/data/bar/
    await expect(tooltip).toContainText(/backtest_catalog\/data\/bar\//)
    // Range uses an arrow between two YYYY-MM-DD dates
    await expect(tooltip).toContainText(/\d{4}-\d{2}-\d{2}\s+→\s+\d{4}-\d{2}-\d{2}/)
    // Bar count is a non-zero number (formatted with optional thousands sep)
    await expect(tooltip).toContainText(/[1-9][\d,]*/)
  })

  test('clicking a chip pins the tooltip open', async ({ page }) => {
    const chip = page.locator('[data-bartype]').first()
    await chip.click()
    // After click, even when the mouse moves away the tooltip stays
    await page.mouse.move(0, 0)
    const tooltip = page.locator('[data-slot="tooltip-content"]').first()
    await expect(tooltip).toBeVisible()
    await expect(chip).toHaveAttribute('data-pinned', 'true')

    // Click again to unpin — tooltip closes after mouse leaves
    await chip.click()
    await expect(chip).not.toHaveAttribute('data-pinned', 'true')
    await page.mouse.move(0, 0)
    await expect(tooltip).not.toBeVisible()
  })
})
```

- [ ] **Step 2: Start the worktree dev servers**

In a separate terminal (or as background processes), start backend + frontend on the worktree ports:

```bash
# Backend
NAUTILUS_STORE_PATH=/Users/mordrax/code/nautilus_automatron/backtest_catalog \
  cd packages/server && .venv/bin/uvicorn server.main:app --port 8003 &

# Frontend
cd packages/client && VITE_API_BASE=http://localhost:8003 bun run dev --port 5176 &
```

Confirm both are listening with `lsof -iTCP:5176 -iTCP:8003 -sTCP:LISTEN`.

- [ ] **Step 3: Run the test headless**

```bash
cd packages/client && TEST_VITE_PORT=5176 TEST_API_PORT=8003 \
  bunx playwright test run-detail-tooltip.spec.ts --project=headless
```

Expected: both `hovering...` and `clicking...` tests PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/client/e2e/run-detail-tooltip.spec.ts
git commit -m "test(client): e2e for bar_type chip tooltip — hover + click-to-pin"
```

---

## Task 7: Final lint + typecheck pass

- [ ] **Step 1: Typecheck client**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 2: Run server tests**

```bash
cd packages/server && .venv/bin/pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 3: Run the full Playwright suite headless (regression sweep)**

```bash
cd packages/client && TEST_VITE_PORT=5176 TEST_API_PORT=8003 \
  bunx playwright test --project=headless
```

Expected: all specs pass — confirms the chip change did not regress `run-detail.spec.ts` or other suites that interact with badges.

- [ ] **Step 4: If any of the above failed, do NOT commit "wip" — fix the underlying issue and re-run. When all three are green, no separate commit is needed (no code changed in this task).**

---

## Self-Review Notes

- **Spec coverage:** Every spec section maps to a task — server fields (Task 1), client type (Task 2), tooltip content (Task 3), chip behavior (Task 4), page wiring (Task 5), Playwright (Task 6), final gates (Task 7).
- **Naming consistency:** `BarTypeChip`, `CatalogTooltipContent`, `catalogMap`, `entry`, `barType` are used identically across tasks. `data-bartype` and `data-pinned` attributes are the test hooks.
- **No placeholders:** every step shows the actual code or command.
