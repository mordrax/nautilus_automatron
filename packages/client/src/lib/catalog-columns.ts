import type { ColumnDefinition } from 'tabulator-tables'
import { stringHeaderFilter, numericHeaderFilter } from '@/lib/run-columns'

export const createCatalogColumns = (): ColumnDefinition[] => [
  {
    title: '',
    formatter: (): string => '<button>View</button>',
    headerSort: false,
    hozAlign: 'center',
    width: 60,
    frozen: true,
  },
  {
    title: 'Instrument',
    field: 'instrument',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: 'Bar Count',
    field: 'bar_count',
    sorter: 'number',
    hozAlign: 'right',
    formatter: (cell) => {
      const value = cell.getValue() as number
      return value.toLocaleString()
    },
    ...numericHeaderFilter,
  },
  {
    title: 'Start Date',
    field: 'start_date',
    sorter: 'string',
    formatter: (cell) => {
      const value = cell.getValue() as string
      if (!value) return '—'
      return new Date(value).toLocaleDateString()
    },
    ...stringHeaderFilter,
  },
  {
    title: 'End Date',
    field: 'end_date',
    sorter: 'string',
    formatter: (cell) => {
      const value = cell.getValue() as string
      if (!value) return '—'
      return new Date(value).toLocaleDateString()
    },
    ...stringHeaderFilter,
  },
  {
    title: 'Timeframe',
    field: 'timeframe',
    sorter: 'string',
    ...stringHeaderFilter,
  },
]
