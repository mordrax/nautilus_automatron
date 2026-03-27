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
  }, [runs, columns])

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
