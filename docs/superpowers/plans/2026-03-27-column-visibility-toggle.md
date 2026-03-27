# Column Visibility Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cog icon to each Tabulator table's title row that opens a popover with column visibility toggles, persisted to localStorage.

**Architecture:** Create a `ColumnVisibilityPopover` React component using Radix Popover + lucide-react Settings icon. Each table component wraps its `<div ref>` in a container with a title bar containing the cog. Column visibility state is managed via a custom hook `useColumnVisibility` that reads/writes localStorage and calls Tabulator's native `showColumn`/`hideColumn` API. The `DashboardPage` title `<h2>` elements move inside the table components to keep the cog co-located with the table it controls.

**Tech Stack:** React, Radix Popover, lucide-react, Tabulator `showColumn`/`hideColumn` API, localStorage

---

### File Structure

| File | Responsibility |
|------|---------------|
| Create: `src/hooks/use-column-visibility.ts` | Custom hook: manages hidden columns set, syncs to localStorage, applies to Tabulator instance |
| Create: `src/components/ui/popover.tsx` | Radix Popover UI component (shadcn/ui pattern) |
| Create: `src/components/table/ColumnVisibilityPopover.tsx` | Cog icon + popover with column toggle checkboxes |
| Modify: `src/components/runs/RunList.tsx` | Add title bar with cog, wire up column visibility |
| Modify: `src/components/catalog/CatalogTable.tsx` | Add title bar with cog, wire up column visibility |
| Modify: `src/pages/DashboardPage.tsx` | Pass titles to table components, remove standalone `<h2>` elements |

---

### Task 1: Create Popover UI component

**Files:**
- Create: `packages/client/src/components/ui/popover.tsx`

- [ ] **Step 1: Create the Popover component**

Create `packages/client/src/components/ui/popover.tsx` following the existing shadcn/ui pattern (see `tooltip.tsx` for the Radix import style):

```tsx
import * as React from "react"
import { Popover as PopoverPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Popover({
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Root>) {
  return <PopoverPrimitive.Root data-slot="popover" {...props} />
}

function PopoverTrigger({
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Trigger>) {
  return <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props} />
}

function PopoverContent({
  className,
  align = "end",
  sideOffset = 4,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        data-slot="popover-content"
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 w-56 origin-(--radix-popover-content-transform-origin) rounded-md border bg-card p-3 shadow-md outline-hidden animate-in fade-in-0 zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          className
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
}

export { Popover, PopoverTrigger, PopoverContent }
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/ui/popover.tsx
git commit -m "feat: add Popover UI component (Radix)"
```

---

### Task 2: Create useColumnVisibility hook

**Files:**
- Create: `packages/client/src/hooks/use-column-visibility.ts`

- [ ] **Step 1: Create the hook**

Create `packages/client/src/hooks/use-column-visibility.ts`:

```ts
import { useState, useCallback, useEffect } from 'react'
import type { TabulatorFull as Tabulator } from 'tabulator-tables'

const STORAGE_PREFIX = 'column-visibility:'

const loadHiddenColumns = (storageKey: string): ReadonlySet<string> => {
  try {
    const stored = localStorage.getItem(`${STORAGE_PREFIX}${storageKey}`)
    if (!stored) return new Set()
    return new Set(JSON.parse(stored) as string[])
  } catch {
    return new Set()
  }
}

const saveHiddenColumns = (storageKey: string, hidden: ReadonlySet<string>): void => {
  localStorage.setItem(
    `${STORAGE_PREFIX}${storageKey}`,
    JSON.stringify([...hidden])
  )
}

export const useColumnVisibility = (storageKey: string) => {
  const [hiddenColumns, setHiddenColumns] = useState<ReadonlySet<string>>(
    () => loadHiddenColumns(storageKey)
  )

  const toggleColumn = useCallback(
    (field: string, table: Tabulator | null) => {
      setHiddenColumns((prev) => {
        const next = new Set(prev)
        if (next.has(field)) {
          next.delete(field)
          table?.showColumn(field)
        } else {
          next.add(field)
          table?.hideColumn(field)
        }
        saveHiddenColumns(storageKey, next)
        return next
      })
    },
    [storageKey]
  )

  const applyVisibility = useCallback(
    (table: Tabulator) => {
      for (const field of hiddenColumns) {
        table.hideColumn(field)
      }
    },
    [hiddenColumns]
  )

  return { hiddenColumns, toggleColumn, applyVisibility } as const
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/hooks/use-column-visibility.ts
git commit -m "feat: add useColumnVisibility hook with localStorage persistence"
```

---

### Task 3: Create ColumnVisibilityPopover component

**Files:**
- Create: `packages/client/src/components/table/ColumnVisibilityPopover.tsx`

- [ ] **Step 1: Create the component**

Create `packages/client/src/components/table/ColumnVisibilityPopover.tsx`:

```tsx
import { Settings } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'

type ColumnInfo = {
  readonly field: string
  readonly title: string
}

type ColumnVisibilityPopoverProps = {
  readonly columns: readonly ColumnInfo[]
  readonly hiddenColumns: ReadonlySet<string>
  readonly onToggle: (field: string) => void
}

export const ColumnVisibilityPopover = ({
  columns,
  hiddenColumns,
  onToggle,
}: ColumnVisibilityPopoverProps) => (
  <Popover>
    <PopoverTrigger asChild>
      <button
        className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        aria-label="Configure columns"
      >
        <Settings className="size-4" />
      </button>
    </PopoverTrigger>
    <PopoverContent className="w-52">
      <div className="space-y-1">
        <p className="text-sm font-medium mb-2">Columns</p>
        {columns.map(({ field, title }) => (
          <label
            key={field}
            className="flex items-center gap-2 text-sm py-0.5 cursor-pointer hover:text-foreground text-muted-foreground has-[:checked]:text-foreground"
          >
            <input
              type="checkbox"
              checked={!hiddenColumns.has(field)}
              onChange={() => onToggle(field)}
              className="accent-primary"
            />
            {title}
          </label>
        ))}
      </div>
    </PopoverContent>
  </Popover>
)
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/table/ColumnVisibilityPopover.tsx
git commit -m "feat: add ColumnVisibilityPopover component"
```

---

### Task 4: Wire up RunList with column visibility

**Files:**
- Modify: `packages/client/src/components/runs/RunList.tsx`

- [ ] **Step 1: Update RunList to include title bar and column visibility**

Replace the contents of `packages/client/src/components/runs/RunList.tsx` with:

```tsx
import { useRef, useEffect, useMemo } from 'react'
import { useLocation } from 'wouter'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { RunSummary } from '@/types/api'
import { createRunColumns } from '@/lib/run-columns'
import { useColumnVisibility } from '@/hooks/use-column-visibility'
import { ColumnVisibilityPopover } from '@/components/table/ColumnVisibilityPopover'

type RunListProps = {
  readonly runs: readonly RunSummary[]
  readonly title: string
}

export const RunList = ({ runs, title }: RunListProps) => {
  const [, setLocation] = useLocation()
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)
  const { hiddenColumns, toggleColumn, applyVisibility } = useColumnVisibility('run-list')

  const columns = useMemo(
    () =>
      createRunColumns((runId: string) => {
        setLocation(`/runs/${runId}`)
      }),
    [setLocation]
  )

  const toggleableColumns = useMemo(
    () =>
      columns
        .filter((col) => col.field)
        .map((col) => ({ field: col.field!, title: col.title ?? col.field! })),
    [columns]
  )

  useEffect(() => {
    if (!tableRef.current) return

    const table = new Tabulator(tableRef.current, {
      data: runs as RunSummary[],
      columns,
      layout: 'fitColumns',
      height: '80vh',
      initialSort: [{ column: 'total_pnl', dir: 'desc' }],
      pagination: true,
      paginationSize: 50,
      paginationSizeSelector: [10, 25, 50, 100],
    })

    table.on('tableBuilt', () => {
      applyVisibility(table)
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [runs, columns, applyVisibility])

  return (
    <div>
      <div className="flex items-center justify-between mb-4 px-2">
        <h2 className="text-xl font-semibold">{title}</h2>
        <ColumnVisibilityPopover
          columns={toggleableColumns}
          hiddenColumns={hiddenColumns}
          onToggle={(field) => toggleColumn(field, tabulatorRef.current)}
        />
      </div>
      <div ref={tableRef} />
    </div>
  )
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: No errors (may fail if DashboardPage hasn't been updated yet — that's OK, we fix it in Task 6)

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/runs/RunList.tsx
git commit -m "feat: add column visibility toggle to RunList"
```

---

### Task 5: Wire up CatalogTable with column visibility

**Files:**
- Modify: `packages/client/src/components/catalog/CatalogTable.tsx`

- [ ] **Step 1: Update CatalogTable to include title bar and column visibility**

Replace the contents of `packages/client/src/components/catalog/CatalogTable.tsx` with:

```tsx
import { useRef, useEffect, useMemo } from 'react'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { CatalogEntry } from '@/types/api'
import { createCatalogColumns } from '@/lib/catalog-columns'
import { useColumnVisibility } from '@/hooks/use-column-visibility'
import { ColumnVisibilityPopover } from '@/components/table/ColumnVisibilityPopover'

type CatalogTableProps = {
  readonly entries: readonly CatalogEntry[]
  readonly title: string
}

export const CatalogTable = ({ entries, title }: CatalogTableProps) => {
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)
  const { hiddenColumns, toggleColumn, applyVisibility } = useColumnVisibility('catalog-table')

  const columns = useMemo(() => createCatalogColumns(), [])

  const toggleableColumns = useMemo(
    () =>
      columns
        .filter((col) => col.field)
        .map((col) => ({ field: col.field!, title: col.title ?? col.field! })),
    [columns]
  )

  useEffect(() => {
    if (!tableRef.current) return

    const table = new Tabulator(tableRef.current, {
      data: entries as CatalogEntry[],
      columns,
      layout: 'fitColumns',
      height: '300px',
      initialSort: [{ column: 'instrument', dir: 'asc' }],
    })

    table.on('tableBuilt', () => {
      applyVisibility(table)
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [entries, columns, applyVisibility])

  return (
    <div>
      <div className="flex items-center justify-between mb-4 px-2">
        <h2 className="text-xl font-semibold">{title}</h2>
        <ColumnVisibilityPopover
          columns={toggleableColumns}
          hiddenColumns={hiddenColumns}
          onToggle={(field) => toggleColumn(field, tabulatorRef.current)}
        />
      </div>
      <div ref={tableRef} />
    </div>
  )
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: No errors (may fail if DashboardPage hasn't been updated yet — that's OK, we fix it in Task 6)

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/catalog/CatalogTable.tsx
git commit -m "feat: add column visibility toggle to CatalogTable"
```

---

### Task 6: Update DashboardPage to pass titles

**Files:**
- Modify: `packages/client/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Update DashboardPage to pass titles to table components and remove standalone h2 elements**

Replace the contents of `packages/client/src/pages/DashboardPage.tsx` with:

```tsx
import { RunList } from '@/components/runs/RunList'
import { CatalogTable } from '@/components/catalog/CatalogTable'
import { useRuns } from '@/hooks/use-runs'
import { useCatalog } from '@/hooks/use-catalog'

export const DashboardPage = () => {
  const { data: runsData, isLoading: runsLoading, error: runsError } = useRuns()
  const { data: catalogData, isLoading: catalogLoading, error: catalogError } = useCatalog()

  return (
    <div className="px-2 py-4 space-y-8">
      <section>
        {catalogLoading && <div className="text-muted-foreground p-4">Loading catalog...</div>}
        {catalogError && <div className="text-destructive p-4">Error loading catalog</div>}
        {catalogData && catalogData.length > 0 && (
          <CatalogTable entries={catalogData} title="Instrument Data Catalog" />
        )}
        {catalogData && catalogData.length === 0 && (
          <div className="text-muted-foreground p-4">No instrument data in catalog</div>
        )}
      </section>

      <section>
        {runsLoading && <div className="text-muted-foreground p-4">Loading runs...</div>}
        {runsError && <div className="text-destructive p-4">Error loading runs</div>}
        {runsData && (
          <RunList
            runs={runsData.runs}
            title={`Backtest Runs ${runsData ? `(${runsData.total})` : ''}`}
          />
        )}
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd packages/client && bunx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Run the dev server and verify visually**

```bash
cd packages/client && bun run dev
```

Open browser, verify both tables render with cog icons in their title bars.

- [ ] **Step 4: Commit**

```bash
git add packages/client/src/pages/DashboardPage.tsx
git commit -m "refactor: pass titles to table components, remove standalone h2 elements"
```
