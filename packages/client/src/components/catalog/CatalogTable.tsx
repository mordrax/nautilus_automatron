import { useRef, useEffect } from 'react'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { CatalogEntry } from '@/types/api'
import { createCatalogColumns } from '@/lib/catalog-columns'

type CatalogTableProps = {
  readonly entries: readonly CatalogEntry[]
}

export const CatalogTable = ({ entries }: CatalogTableProps) => {
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)

  useEffect(() => {
    if (!tableRef.current) return

    const table = new Tabulator(tableRef.current, {
      data: entries as CatalogEntry[],
      columns: createCatalogColumns(),
      layout: 'fitColumns',
      height: '300px',
      initialSort: [{ column: 'instrument', dir: 'asc' }],
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [entries])

  return <div ref={tableRef} />
}
