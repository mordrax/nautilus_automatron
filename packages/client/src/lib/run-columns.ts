import type { CellComponent, ColumnDefinition } from 'tabulator-tables'

// --- Formatters ---

const pnlFormatter = (cell: CellComponent): string => {
  const value = cell.getValue() as number | null
  if (value === null || value === undefined) return '—'
  const color = value >= 0 ? 'green' : 'red'
  const sign = value >= 0 ? '+' : ''
  return `<span style="color:${color}">${sign}${value.toFixed(2)}</span>`
}

const percentFormatter = (cell: CellComponent): string => {
  const value = cell.getValue() as number | null
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

const currencyFormatter = (cell: CellComponent): string => {
  const value = cell.getValue() as number | null
  if (value === null || value === undefined) return '—'
  return value.toFixed(2)
}

const hoursFormatter = (cell: CellComponent): string => {
  const value = cell.getValue() as number | null
  if (value === null || value === undefined) return '—'
  return `${value}h`
}

const ratioFormatter = (cell: CellComponent): string => {
  const value = cell.getValue() as number | null
  if (value === null || value === undefined) return '—'
  return value.toFixed(2)
}

const winsLossesFormatter = (cell: CellComponent): string => {
  const row = cell.getRow().getData() as { wins: number | null; losses: number | null }
  if (row.wins === null || row.wins === undefined || row.losses === null || row.losses === undefined) return '—'
  return `${row.wins} / ${row.losses}`
}

// --- Header Filters ---

const numericHeaderFilterFunc = (
  headerValue: string,
  _rowValue: unknown,
  rowData: unknown,
  filterParams: { field: string }
): boolean => {
  const raw = String(headerValue).trim()
  if (!raw) return true

  const rowVal = (rowData as Record<string, unknown>)[filterParams.field]
  const num = typeof rowVal === 'number' ? rowVal : parseFloat(String(rowVal))
  if (isNaN(num)) return false

  if (raw.startsWith('>=')) return num >= parseFloat(raw.slice(2))
  if (raw.startsWith('<=')) return num <= parseFloat(raw.slice(2))
  if (raw.startsWith('>')) return num > parseFloat(raw.slice(1))
  if (raw.startsWith('<')) return num < parseFloat(raw.slice(1))
  if (raw.startsWith('=')) return num === parseFloat(raw.slice(1))

  return num === parseFloat(raw)
}

export const numericHeaderFilter = {
  headerFilter: 'input' as const,
  headerFilterFunc: numericHeaderFilterFunc,
}

const stringHeaderFilterFunc = (
  headerValue: string,
  rowValue: unknown
): boolean => {
  if (!headerValue) return true
  return String(rowValue).toLowerCase().includes(String(headerValue).toLowerCase())
}

export const stringHeaderFilter = {
  headerFilter: 'input' as const,
  headerFilterFunc: stringHeaderFilterFunc,
}

// --- Column Definitions ---

export const createRunColumns = (onViewRun: (runId: string) => void): ColumnDefinition[] => [
  {
    title: 'Run ID',
    field: 'run_id',
    sorter: 'string',
    ...stringHeaderFilter,
    width: 120,
    formatter: (cell: CellComponent): string => {
      const value = cell.getValue() as string
      if (!value) return '—'
      return `<span style="font-family:monospace">${value.slice(0, 8)}...</span>`
    },
  },
  {
    title: 'Trader',
    field: 'trader_id',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: 'Strategy',
    field: 'strategy',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: 'Positions',
    field: 'total_positions',
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Fills',
    field: 'total_fills',
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Total PnL',
    field: 'total_pnl',
    sorter: 'number',
    hozAlign: 'right',
    formatter: pnlFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Win Rate',
    field: 'win_rate',
    sorter: 'number',
    hozAlign: 'right',
    formatter: percentFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Expectancy',
    field: 'expectancy',
    sorter: 'number',
    hozAlign: 'right',
    formatter: currencyFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Sharpe',
    field: 'sharpe_ratio',
    sorter: 'number',
    hozAlign: 'right',
    formatter: ratioFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Avg Win',
    field: 'avg_win',
    sorter: 'number',
    hozAlign: 'right',
    formatter: currencyFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Avg Loss',
    field: 'avg_loss',
    sorter: 'number',
    hozAlign: 'right',
    formatter: pnlFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'W/L Ratio',
    field: 'win_loss_ratio',
    sorter: 'number',
    hozAlign: 'right',
    formatter: ratioFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'W / L',
    field: 'wins',
    sorter: 'number',
    hozAlign: 'center',
    formatter: winsLossesFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Avg Hold',
    field: 'avg_hold_hours',
    sorter: 'number',
    hozAlign: 'right',
    formatter: hoursFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'PnL/Week',
    field: 'pnl_per_week',
    sorter: 'number',
    hozAlign: 'right',
    formatter: pnlFormatter,
    ...numericHeaderFilter,
  },
  {
    title: 'Trades/Week',
    field: 'trades_per_week',
    sorter: 'number',
    hozAlign: 'right',
    formatter: ratioFormatter,
    ...numericHeaderFilter,
  },
  {
    title: '',
    field: 'run_id',
    headerSort: false,
    headerFilter: undefined,
    hozAlign: 'center',
    width: 70,
    formatter: (): string => '<button>View</button>',
    cellClick: (_e: UIEvent, cell: CellComponent) => {
      onViewRun(cell.getValue() as string)
    },
  },
]
