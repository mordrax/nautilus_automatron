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

const evalFilter = (cellValue: number, filter: string): boolean => {
  const trimmed = filter.trim()
  if (trimmed.startsWith('>=')) {
    const t = parseFloat(trimmed.slice(2))
    return !isNaN(t) && cellValue >= t
  }
  if (trimmed.startsWith('<=')) {
    const t = parseFloat(trimmed.slice(2))
    return !isNaN(t) && cellValue <= t
  }
  if (trimmed.startsWith('>')) {
    const t = parseFloat(trimmed.slice(1))
    return !isNaN(t) && cellValue > t
  }
  if (trimmed.startsWith('<')) {
    const t = parseFloat(trimmed.slice(1))
    return !isNaN(t) && cellValue < t
  }
  if (trimmed.startsWith('=')) {
    const t = parseFloat(trimmed.slice(1))
    return !isNaN(t) && cellValue === t
  }
  const t = parseFloat(trimmed)
  return isNaN(t) || cellValue === t
}

const numericFilterFn = (headerValue: string, rowValue: unknown): boolean => {
  const raw = String(headerValue).trim()
  if (!raw) return true
  const num = typeof rowValue === 'number' ? rowValue : parseFloat(String(rowValue))
  if (isNaN(num)) return false
  return evalFilter(num, raw)
}

const percentFilterFn = (headerValue: string, rowValue: unknown): boolean => {
  const raw = String(headerValue).trim()
  if (!raw) return true
  const num = typeof rowValue === 'number' ? rowValue : parseFloat(String(rowValue))
  if (isNaN(num)) return false
  return evalFilter(num * 100, raw)
}

export const numericHeaderFilter = {
  headerFilter: true as const,
  headerFilterFunc: numericFilterFn,
}

const percentHeaderFilter = {
  headerFilter: true as const,
  headerFilterFunc: percentFilterFn,
}

const stringHeaderFilterFunc = (
  headerValue: string,
  rowValue: unknown
): boolean => {
  if (!headerValue) return true
  return String(rowValue).toLowerCase().includes(String(headerValue).toLowerCase())
}

export const stringHeaderFilter = {
  headerFilter: true as const,
  headerFilterFunc: stringHeaderFilterFunc,
}

// --- Column Definitions ---

export const createActionColumns = (
  onRerun: (runId: string) => void,
  onDelete: (runId: string) => void,
): ColumnDefinition[] => [
  {
    title: '',
    formatter: (): string => '<button title="Rerun" style="cursor:pointer">↻</button>',
    headerSort: false,
    hozAlign: 'center',
    width: 40,
    cellClick: (_e: UIEvent, cell: CellComponent) => {
      const data = cell.getRow().getData() as { run_id: string }
      onRerun(data.run_id)
    },
  },
  {
    title: '',
    formatter: (): string => '<button title="Delete" style="cursor:pointer;color:red">✕</button>',
    headerSort: false,
    hozAlign: 'center',
    width: 40,
    cellClick: (_e: UIEvent, cell: CellComponent) => {
      const data = cell.getRow().getData() as { run_id: string }
      if (confirm(`Delete run ${data.run_id.slice(0, 8)}...?`)) {
        onDelete(data.run_id)
      }
    },
  },
]

export const createRunColumns = (onViewRun: (runId: string) => void): ColumnDefinition[] => [
  {
    title: '',
    formatter: (): string => '<button>View</button>',
    headerSort: false,
    hozAlign: 'center',
    width: 60,
    frozen: true,
    cellClick: (_e: UIEvent, cell: CellComponent) => {
      const data = cell.getRow().getData() as { run_id: string }
      onViewRun(data.run_id)
    },
  },
  {
    title: 'Trader',
    field: 'trader_id',
    sorter: 'string',
    ...stringHeaderFilter,
    minWidth: 150,
  },
  {
    title: 'Strategy',
    field: 'strategy',
    sorter: 'string',
    ...stringHeaderFilter,
    minWidth: 150,
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
    ...percentHeaderFilter,
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
]
