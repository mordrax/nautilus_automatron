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
  readonly onViewInstrument: (barType: string) => void
}

export const CatalogTable = ({ entries, title, onViewInstrument }: CatalogTableProps) => {
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)
  const { hiddenColumns, toggleColumn, applyVisibility } = useColumnVisibility('catalog-table')

  const columns = useMemo(() => createCatalogColumns(onViewInstrument), [onViewInstrument])

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
