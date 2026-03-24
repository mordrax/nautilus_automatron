# Nautilus Automatron

Backtest analysis dashboard for [NautilusTrader](https://github.com/nautechsystems/nautilus_trader). Browse, visualize, and navigate backtest runs produced by NautilusTrader's streaming catalog.

## Architecture

- **Backend**: FastAPI server that reads NautilusTrader's StreamingConfig catalog format (Arrow IPC / feather files)
- **Frontend**: React + Vite + eCharts for interactive candlestick charts with trade overlays

### Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI, PyArrow, NautilusTrader |
| Frontend | React 19, Vite, TypeScript, Effect-TS |
| Charting | eCharts |
| UI | shadcn/ui, Tailwind CSS, Radix UI |
| Routing | wouter |
| Data fetching | TanStack React Query |
| Package manager | Bun (monorepo) |

## Getting Started

### Prerequisites

- [Bun](https://bun.sh/)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- A NautilusTrader backtest catalog directory

### Install

```bash
bun install
cd packages/server && uv sync
```

### Run

```bash
# Set the path to your NautilusTrader backtest catalog
export NAUTILUS_STORE_PATH=/path/to/your/backtest_catalog

# Start both frontend and backend
bun run dev
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

## Project Structure

```
packages/
  client/          # React + Vite frontend
    src/
      components/  # UI components (chart, runs, trades)
      hooks/       # Custom React hooks
      lib/         # API client, utilities
      pages/       # Route pages
      types/       # TypeScript type definitions
  server/          # FastAPI backend
    server/
      routes/      # API endpoints
      store/       # Data reading and transformation
```
