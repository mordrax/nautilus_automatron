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
