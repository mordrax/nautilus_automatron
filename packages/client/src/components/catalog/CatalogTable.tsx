import { useRef, useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { TabulatorFull as Tabulator, type RowComponent } from 'tabulator-tables'
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
  const [isOpen, setIsOpen] = useState(true)
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

    table.on('rowClick', (_e: UIEvent, row: RowComponent) => {
      const data = row.getData() as { bar_type: string }
      onViewInstrument(data.bar_type)
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [entries, columns, applyVisibility, onViewInstrument])

  return (
    <div>
      <div className="flex items-center justify-between mb-4 px-2">
        <button
          type="button"
          onClick={() => setIsOpen((v) => !v)}
          className="flex items-center gap-2 text-xl font-semibold hover:opacity-80"
          aria-expanded={isOpen}
          aria-label={isOpen ? `Collapse ${title}` : `Expand ${title}`}
        >
          {isOpen ? <ChevronDown className="size-5" /> : <ChevronRight className="size-5" />}
          <h2>{title}</h2>
        </button>
        {isOpen && (
          <ColumnVisibilityPopover
            columns={toggleableColumns}
            hiddenColumns={hiddenColumns}
            onToggle={(field) => toggleColumn(field, tabulatorRef.current)}
          />
        )}
      </div>
      <div ref={tableRef} style={{ display: isOpen ? undefined : 'none' }} />
    </div>
  )
}
