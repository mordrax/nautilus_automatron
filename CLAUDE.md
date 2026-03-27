# Nautilus Automatron

Backtest analysis dashboard for NautilusTrader.

## Architecture
- Bun monorepo with packages/client (React+Vite) and packages/server (FastAPI)
- Frontend: React + Vite + Bun + Effect-TS + eCharts + shadcn/ui
- Backend: FastAPI serving data from NautilusTrader catalog (feather files)

## Functional Programming - ENFORCED
- NO classes anywhere except Pydantic models
- Python: pure functions, functools, composition
- TypeScript: Effect pipe/flow, functional components, custom hooks
- See global CLAUDE.md for full rules

## Backend
- Store path configured via STORE_PATH env var
- Reads NautilusTrader StreamingConfig catalog format (feather files)
- All route handlers are plain functions with dependency injection

## Frontend
- All API calls through Effect-TS wrapped in React Query
- eCharts for all charting (not Recharts)
- shadcn/ui new-york style, neutral base color
- wouter for routing

## Backtest Catalog
- Located at `./backtest_catalog/` (gitignored, contains ~95MB of feather data)
- Configured via `NAUTILUS_STORE_PATH` env var (defaults to `./backtest_catalog`)
- Contains NautilusTrader StreamingConfig output: UUID-named run dirs with config.json + feather files
- E2e test data is separate at `packages/client/e2e/test-data/`

## Strategies
- Trading strategies live in a separate private package: `nautilus_strategies` at `/Users/mordrax/code/nautilus_strategies`
- `nautilus_strategies` is a pure library — strategies only, no data, no I/O. Depends on `nautilus_trader` for base classes.
- Dependency chain: `nautilus_trader` ← `nautilus_strategies` ← `nautilus_automatron`
- nautilus_automatron imports strategies and handles all data loading and engine orchestration
- The runner package (`packages/runner`) orchestrates backtests via Jupyter notebooks
- To run a backtest: open `packages/runner/runner/run_backtest.ipynb`
