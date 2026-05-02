# Nautilus Automatron — Client

React frontend for the backtest analysis dashboard.

## Tech Stack

- **React 19** with TypeScript
- **Vite** for build and dev server
- **Effect-TS** for functional API composition
- **TanStack React Query** for server state management
- **eCharts** for all charting (candlestick, equity curve, P&L distribution, etc.)
- **Tabulator** for sortable/filterable data tables
- **shadcn/ui** (Radix UI primitives + Tailwind CSS v4) for UI components
- **wouter** for client-side routing

## Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `DashboardPage` | Lists all backtest runs with metrics table and instrument catalog |
| `/runs/:runId` | `RunDetailPage` | Interactive chart with trade overlays, trade navigation, indicators, and analysis tabs |
| `/create` | `CreateBacktestPage` | Form to create a new backtest (strategy + bar type + params) |
| `/instruments/:barType` | `InstrumentPage` | View raw catalog bar data for an instrument |

## Components

### Charts
- **CandlestickChart** — OHLCV candlestick chart with trade entry/exit markers, zoom/pan, and indicator overlays
- **EquityCurveChart** — Account equity over time
- **PnlDistributionChart** — Histogram of trade P&L values
- **PnlHoldTimeChart** — Scatter plot: P&L vs hold duration
- **PnlOverTimeChart** — Cumulative P&L progression
- **TradesByMonthChart** — Bar chart grouping trades by month
- **IndicatorToggles** — Checkbox controls for overlays (SMA, EMA, BB) and panels (RSI, MACD, ATR)

### Tables
- **RunList** — Tabulator table with all run metrics, View/Rerun/Delete buttons, column visibility control
- **CatalogTable** — Instrument data catalog with bar counts and date ranges
- **TradeTable** — All trades with entry/exit details, direction, P&L
- **CategorisationTable** — Trade categorization with tags

### Navigation
- **TradeNavigator** — Prev/Next buttons for stepping through trades on the chart
- **AppLayout** — Header with version indicator and backend health check

## Hooks

| Hook | Purpose |
|------|---------|
| `useRuns` | Paginated run list |
| `useRunDetail` | Run metadata, bar types, trades, equity |
| `useTrades` | Trade data for a run |
| `useCatalog` | Instrument catalog entries |
| `useCatalogBars` | Raw bar data from catalog |
| `useStrategies` | Available strategies for create form |
| `useCatalogBarTypes` | Bar types from data catalog |
| `useIndicators` | Indicator toggle state and computation |
| `useCreateBacktest` | Mutation: create new backtest |
| `useRerunBacktest` | Mutation: rerun existing backtest |
| `useDeleteBacktest` | Mutation: delete backtest run |
| `useHotkeys` | Keyboard shortcuts (trade navigation) |
| `useColumnVisibility` | Table column show/hide state |
| `useCategorisation` | Trade categorization state |

## API Client

All API calls go through `lib/api.ts` using Effect-TS:

```typescript
// Fetch with error handling
const fetchJson = <T>(url: string): Effect.Effect<T, ApiError> => ...

// Run an Effect and convert to Promise (for React Query)
export const runEffect = <T>(effect: Effect.Effect<T, ApiError>): Promise<T> => ...

// Usage in hooks:
export const useRuns = (page: number = 1) =>
  useQuery({
    queryKey: ['runs', page],
    queryFn: () => api.runEffect(api.getRuns(page)),
  })
```

The Vite dev server proxies `/api` requests to the backend (configured in `vite.config.ts`).

## Testing

```bash
# Headless (CI)
npx playwright test --project=headless

# UI mode (interactive)
npx playwright test --ui

# Headed (visible browser, slow motion)
npx playwright test --project=headed
```

Test data lives in `e2e/test-data/backtest_catalog/` — a small catalog with one AUDUSD backtest run.

### Test Files

| File | Tests |
|------|-------|
| `runs-page.spec.ts` | Dashboard rendering, filtering, sorting |
| `run-detail.spec.ts` | Run detail page layout and badges |
| `navigation.spec.ts` | Trade Prev/Next navigation |
| `chart-analysis.spec.ts` | P&L charts rendering |
| `trade-analysis-tabs.spec.ts` | Tab switching |
| `trade-zoom.spec.ts` | Chart zoom on trade selection |
| `indicators.spec.ts` | Indicator toggle and chart resize |
| `trades-by-month.spec.ts` | Monthly trades chart |
| `categorisation.spec.ts` | Trade categorization UI |
| `column-visibility.spec.ts` | Column show/hide |
| `visual.spec.ts` | Visual regression snapshots |
| `backtest-crud.spec.ts` | Create/delete backtest flow |
