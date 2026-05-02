# Nautilus Automatron

Backtest analysis dashboard for [NautilusTrader](https://github.com/nautechsystems/nautilus_trader). Browse, visualize, and manage backtest runs produced by NautilusTrader's streaming catalog.

## Features

- **Dashboard** — browse all backtest runs with sortable/filterable metrics (PnL, win rate, Sharpe ratio, expectancy)
- **Run Detail** — interactive candlestick chart with trade entry/exit overlays, trade navigation, and technical indicators
- **Trade Analysis** — P&L distribution, hold time scatter, equity curve, trades by month
- **Technical Indicators** — SMA, EMA, HMA, Bollinger Bands, Donchian Channel, RSI, MACD, ATR, Stochastics
- **Backtest CRUD** — create new backtests from the UI, rerun existing ones, delete stale runs
- **Instrument Catalog** — view available market data with bar counts and date ranges

## Architecture

```
packages/
  client/     React + Vite frontend
  server/     FastAPI backend (reads NautilusTrader catalog)
  runner/     Backtest execution (wraps NautilusTrader BacktestNode)
  data/       Market data ingestion utilities
```

### Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI, PyArrow, NautilusTrader, ParquetDataCatalog |
| Frontend | React 19, Vite, TypeScript, Effect-TS |
| Charting | eCharts |
| UI | shadcn/ui, Tailwind CSS v4, Radix UI |
| Routing | wouter |
| Data Fetching | TanStack React Query |
| Tables | Tabulator |
| Package Manager | Bun (monorepo), uv (Python) |

### Data Flow

```
Backtest Catalog (Parquet/feather files)
  → ParquetDataCatalog (NautilusTrader)
  → FastAPI routes (pure functions with dependency injection)
  → JSON API
  → Effect-TS API client
  → React Query hooks
  → eCharts / Tabulator / shadcn components
```

## Getting Started

### Prerequisites

- [Bun](https://bun.sh/) (JavaScript runtime and package manager)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- A NautilusTrader backtest catalog directory

### Install

```bash
# Install frontend dependencies
bun install

# Install backend dependencies
cd packages/runner && uv venv && uv pip install -e .
cd ../server && uv venv && uv pip install -e ../runner && uv pip install -e .
```

### Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env to set your catalog path
# NAUTILUS_STORE_PATH=/path/to/your/backtest_catalog
```

### Run

```bash
bun run dev
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

### Optional: Add Private Strategies

If you have a private strategies package (e.g., `nautilus_strategies`):

```bash
./scripts/setup-local.sh
```

This installs the private package and creates `packages/runner/runner/strategies_local.py` which registers additional strategies in the UI dropdown. See `strategies_local.py.example` for the format.

## Project Structure

```
nautilus_automatron/
├── packages/
│   ├── client/                 # React + Vite frontend
│   │   ├── src/
│   │   │   ├── components/     # UI components
│   │   │   ├── hooks/          # React Query hooks
│   │   │   ├── lib/            # API client, column defs, chart config
│   │   │   ├── pages/          # Route pages
│   │   │   └── types/          # TypeScript types
│   │   └── e2e/                # Playwright tests
│   ├── server/                 # FastAPI backend
│   │   └── server/
│   │       ├── routes/         # API endpoints
│   │       └── store/          # Data reading and transformation
│   ├── runner/                 # Backtest execution
│   │   └── runner/
│   │       ├── backtest.py     # BacktestNode wrapper
│   │       ├── registry.py     # Strategy registry
│   │       └── migrate.py      # Data migration tool
│   └── data/                   # Market data ingestion
├── scripts/
│   └── setup-local.sh          # Private dependency setup
├── backtest_catalog/           # Data directory (gitignored)
└── .github/workflows/          # CI pipeline
```

## API Reference

### Runs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/runs` | List backtest runs (paginated) |
| GET | `/api/runs/{run_id}` | Get run metadata and bar types |
| POST | `/api/runs` | Create and execute a new backtest |
| POST | `/api/runs/{run_id}/rerun` | Rerun a backtest from saved config |
| DELETE | `/api/runs/{run_id}` | Delete a backtest run |

### Run Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/runs/{run_id}/bars` | List bar types in a run |
| GET | `/api/runs/{run_id}/bars/{bar_type}` | Get OHLCV bar data |
| GET | `/api/runs/{run_id}/fills` | Get order fill events |
| GET | `/api/runs/{run_id}/trades` | Get trades (entry/exit pairs with P&L) |
| GET | `/api/runs/{run_id}/positions` | Get closed positions |
| GET | `/api/runs/{run_id}/account` | Get account state history |
| GET | `/api/runs/{run_id}/equity` | Get equity curve |

### Indicators

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/indicators` | List available indicators |
| GET | `/api/runs/{run_id}/bars/{bar_type}/indicators?ids=...` | Compute indicators on bar data |

### Catalog & Strategies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/catalog` | List available instruments in data catalog |
| GET | `/api/strategies` | List available strategies with defaults |
| GET | `/api/bar-types` | List bar types from data catalog |

## Backtest Catalog

The catalog directory (`NAUTILUS_STORE_PATH`) contains two sections:

```
backtest_catalog/
├── data/                           # Source market data
│   ├── bar/{bar_type}/*.parquet    # Historical OHLCV bars
│   └── currency_pair/{id}/         # Instrument definitions
└── backtest/                       # Backtest results
    └── {run_id}/
        ├── config.json             # Engine config
        ├── run_config.json         # Strategy config (for rerun)
        └── *.feather               # Fills, positions, bars, account states
```

- `data/` contains source market data written via `ParquetDataCatalog.write_data()`
- `backtest/` contains run results written automatically by NautilusTrader's `StreamingConfig`
- The catalog is gitignored — not part of the repository

## Strategies

The runner ships with NautilusTrader's built-in **EMACross** strategy. Additional strategies can be added via a gitignored local config file:

1. **Built-in strategies** are defined in `packages/runner/runner/registry.py`
2. **Private strategies** are loaded from `packages/runner/runner/strategies_local.py` (gitignored)
3. Run `./scripts/setup-local.sh` to set up private strategies automatically
4. See `strategies_local.py.example` for the registration format

## Development

### Scripts

```bash
bun run dev              # Start frontend + backend
bun run dev:client       # Frontend only
bun run dev:server       # Backend only
bun run build            # Build frontend
bun run test:e2e         # Run Playwright tests (headless)
bun run test:e2e:headed  # Run Playwright tests (visible browser)
bun run kill             # Free development ports
```

### Testing

```bash
# Frontend E2E tests
cd packages/client && npx playwright test --project=headless

# Python unit tests
cd packages/runner && uv run pytest tests/ -v
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NAUTILUS_PORT` | `8000` | Backend API port |
| `NAUTILUS_STORE_PATH` | `./backtest_catalog` | Path to NautilusTrader catalog |
| `VITE_PORT` | `5173` | Frontend dev server port |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL for Vite proxy |
| `NAUTILUS_STRATEGIES_PATH` | `/Users/mordrax/code/nautilus_strategies` | Path to private strategies repo (optional) |

## CI/CD

GitHub Actions runs on pull requests to `main`:

1. **Lint** — TypeScript type checking and ESLint
2. **E2E** — Full Playwright test suite against a test data catalog
   - Auto-updates visual regression baselines for Linux
   - Uploads Playwright report on failure
