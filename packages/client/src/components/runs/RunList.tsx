import { useRef, useEffect } from 'react'
import { useLocation } from 'wouter'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { RunSummary } from '@/types/api'
import { createRunColumns, createActionColumns } from '@/lib/run-columns'

type RunListProps = {
  readonly runs: readonly RunSummary[]
  readonly onRerun: (runId: string) => void
  readonly onDelete: (runId: string) => void
}

export const RunList = ({ runs, onRerun, onDelete }: RunListProps) => {
  const [, setLocation] = useLocation()
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)

  useEffect(() => {
    if (!tableRef.current) return

    const columns = [
      ...createRunColumns((runId: string) => setLocation(`/runs/${runId}`)),
      ...createActionColumns(onRerun, onDelete),
    ]

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

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [runs, setLocation, onRerun, onDelete])

  return <div ref={tableRef} />
}
