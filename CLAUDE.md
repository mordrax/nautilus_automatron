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
