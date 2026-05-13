import { useRef, useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useLocation } from 'wouter'
import { TabulatorFull as Tabulator, type RowComponent } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { RunSummary } from '@/types/api'
import { createRunColumns, createActionColumns } from '@/lib/run-columns'
import { useColumnVisibility } from '@/hooks/use-column-visibility'
import { ColumnVisibilityPopover } from '@/components/table/ColumnVisibilityPopover'

type RunListProps = {
  readonly runs: readonly RunSummary[]
  readonly title: string
  readonly onRerun: (runId: string) => void
  readonly onDelete: (runId: string) => void
}

export const RunList = ({ runs, title, onRerun, onDelete }: RunListProps) => {
  const [, setLocation] = useLocation()
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)
  const [isOpen, setIsOpen] = useState(true)
  const { hiddenColumns, toggleColumn, applyVisibility } = useColumnVisibility('run-list')

  const columns = useMemo(
    () => [
      ...createRunColumns((runId: string) => {
        setLocation(`/runs/${runId}`)
      }),
      ...createActionColumns(onRerun, onDelete),
    ],
    [setLocation, onRerun, onDelete]
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

    table.on('rowClick', (_e: UIEvent, row: RowComponent) => {
      const data = row.getData() as { run_id: string }
      setLocation(`/runs/${data.run_id}`)
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- setLocation from wouter is stable
  }, [runs, columns, applyVisibility])

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
