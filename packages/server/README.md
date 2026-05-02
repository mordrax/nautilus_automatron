# Nautilus Automatron — Server

FastAPI backend that reads NautilusTrader's backtest catalog and serves data to the frontend.

## Tech Stack

- **FastAPI** with Uvicorn (ASGI)
- **NautilusTrader** `ParquetDataCatalog` for data access
- **PyArrow** for Arrow IPC / Parquet file reading
- **Pydantic Settings** for configuration (`NAUTILUS_` env prefix)
- Python 3.12+

## API Endpoints

### Runs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/runs?page=1&per_page=20` | List runs with pagination and metrics |
| GET | `/api/runs/{run_id}` | Run metadata, config, bar types |
| POST | `/api/runs` | Create and execute a new backtest |
| POST | `/api/runs/{run_id}/rerun` | Rerun from saved `run_config.json` |
| DELETE | `/api/runs/{run_id}` | Delete a run directory |

### Run Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/runs/{run_id}/bars` | List bar types in a run |
| GET | `/api/runs/{run_id}/bars/{bar_type}` | OHLCV bar data (columnar JSON) |
| GET | `/api/runs/{run_id}/fills` | OrderFilled events |
| GET | `/api/runs/{run_id}/trades` | Trades (fills grouped into entry/exit pairs with P&L) |
| GET | `/api/runs/{run_id}/positions` | PositionClosed events |
| GET | `/api/runs/{run_id}/account` | AccountState history |
| GET | `/api/runs/{run_id}/equity` | Equity curve (timestamp + balance) |

### Indicators

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/indicators` | List available indicators with metadata |
| GET | `/api/runs/{run_id}/bars/{bar_type}/indicators?ids=rsi_14,bb_20_2` | Compute indicators on bar data |

Available indicators: SMA, EMA, HMA, Bollinger Bands, Donchian Channel, RSI, MACD, ATR, Stochastics.

### Catalog & Strategies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/catalog` | Instrument catalog (bar counts, date ranges) |
| GET | `/api/catalog/bars/{bar_type}` | Raw catalog OHLCV data |
| GET | `/api/strategies` | Available strategies with default params |
| GET | `/api/bar-types` | Bar types from data catalog |
| GET | `/api/version` | Server version |

## Architecture

### Routes (pure functions)

Every route handler is a plain function with dependency injection:

```python
@router.get("/runs")
def list_runs(
    page: int = 1,
    per_page: int = 20,
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    ...
```

### Store Layer

Pure transformation functions — no side effects except at I/O boundaries:

- **catalog_reader.py** — filters mixed data from `ParquetDataCatalog.read_backtest()` into typed lists (fills, positions, bars, account states)
- **reader.py** — file system operations: read `config.json`, scan catalog entries, delete runs
- **transforms.py** — converts NautilusTrader objects to JSON-serializable dicts
- **indicators.py** — typed indicator registry with compute functions
- **metrics.py** — trade performance metrics (win rate, Sharpe ratio, expectancy, etc.)

### Data Access

The server uses NautilusTrader's `ParquetDataCatalog` to read backtest results:

```python
catalog = ParquetDataCatalog(store_path)
data = catalog.read_backtest(run_id)  # Returns mixed list of all data types
fills = [d for d in data if isinstance(d, OrderFilled)]
bars = [d for d in data if isinstance(d, Bar)]
```

### Configuration

Settings via Pydantic `BaseSettings` with `NAUTILUS_` env prefix:

| Setting | Env Var | Default |
|---------|---------|---------|
| `store_path` | `NAUTILUS_STORE_PATH` | `./backtest_catalog` |
| `port` | `NAUTILUS_PORT` | `8000` |

Reads from `.env` file at project root (3 levels up from `config.py`).

## Running

```bash
# With the monorepo dev script (recommended)
cd ../.. && bun run dev:server

# Directly
.venv/bin/uvicorn server.main:app --reload --port 8000

# With custom catalog path
NAUTILUS_STORE_PATH=/path/to/catalog .venv/bin/uvicorn server.main:app --port 8000
```

## CRUD Endpoints

The create/rerun endpoints lazily import from the `runner` package. This means:

- The server starts without the runner installed (for CI and lightweight deployments)
- CRUD endpoints only work when the runner package is installed in the server's venv
- The runner is installed automatically by `scripts/setup-local.sh` or `uv pip install -e ../runner`
