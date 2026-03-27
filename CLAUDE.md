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
- Store path configured via NAUTILUS_STORE_PATH env var
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
- Built-in: EMACross from nautilus_trader (always available, used in CI)
- Private strategies: imported via `packages/runner/runner/strategies_local.py` (gitignored)
- To add private strategies: run `./scripts/setup-local.sh` or manually:
  1. `uv pip install -e /path/to/nautilus_strategies`
  2. Copy `strategies_local.py.example` to `strategies_local.py` and uncomment
- The runner package has NO dependency on nautilus_strategies in pyproject.toml
- CI uses only the built-in EMACross strategy
