# Interactive Brokers Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Jupyter notebook in the runner package that connects to Interactive Brokers via DockerizedIBGateway and interactively pulls historical bar data (1-min, 5-min examples for XAUUSD) into CSV files consumable by the existing backtest workflow.

**Architecture:** The runner package gets IB-specific dependencies (`nautilus_trader[ib]`, `docker`) pinned to Python 3.13 (ibapi requires <3.14). A single Jupyter notebook provides an interactive UI for connecting to IB, selecting instruments/timeframes, and saving data. Docker IB Gateway handles authentication via `TWS_USERNAME`/`TWS_PASSWORD` env vars from a `.env.ib` file.

**Tech Stack:** NautilusTrader IB adapter (`HistoricInteractiveBrokersClient`, `DockerizedIBGateway`), Python 3.13, Jupyter, pandas, Docker

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `packages/runner/pyproject.toml` | Runner package with IB deps, pinned to Python 3.13 |
| Create | `packages/runner/runner/__init__.py` | Package init |
| Create | `packages/runner/.env.ib.example` | Template for IB credentials |
| Create | `packages/runner/.env.ib` | Actual IB credentials (gitignored) |
| Create | `packages/runner/runner/ib_data_pull.ipynb` | Interactive notebook for pulling IB historical data |
| Modify | `.gitignore` | Add `.env.ib` pattern |
| Create | `data/` | Directory for downloaded CSV data files |

---

### Task 1: Set up runner package with IB dependencies

**Files:**
- Create: `packages/runner/pyproject.toml`
- Create: `packages/runner/runner/__init__.py`

- [ ] **Step 1: Create runner pyproject.toml with IB dependencies**

```toml
[project]
name = "nautilus-automatron-runner"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = [
    "nautilus_trader",
    "nautilus-ibapi==10.43.2",
    "protobuf==5.29.5",
    "docker>=7.0.0",
    "pandas>=2.2.0",
    "pyarrow>=18.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "jupyter>=1.0.0",
    "ipykernel>=6.0.0",
]

[tool.hatch.build.targets.wheel]
packages = ["runner"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create runner/__init__.py**

```python
"""Nautilus Automatron Runner — backtest execution and data ingestion."""
```

- [ ] **Step 3: Create venv with Python 3.13 and install dependencies**

```bash
cd packages/runner
uv venv --python python3.13
uv sync --all-extras
```

- [ ] **Step 4: Verify IB adapter imports work**

```bash
cd packages/runner
uv run python -c "from nautilus_trader.adapters.interactive_brokers.historical.client import HistoricInteractiveBrokersClient; print('IB adapter OK')"
```

Expected: `IB adapter OK`

- [ ] **Step 5: Commit**

```bash
git add packages/runner/pyproject.toml packages/runner/runner/__init__.py packages/runner/uv.lock
git commit -m "feat(runner): set up runner package with IB adapter dependencies"
```

---

### Task 2: Configure IB credentials and gitignore

**Files:**
- Create: `packages/runner/.env.ib.example`
- Create: `packages/runner/.env.ib`
- Modify: `.gitignore`

- [ ] **Step 1: Create .env.ib.example template**

```env
# Interactive Brokers credentials for DockerizedIBGateway
# Copy this file to .env.ib and fill in your credentials
TWS_USERNAME=your_ib_username
TWS_PASSWORD=your_ib_password
```

- [ ] **Step 2: Ask user for IB credentials and create .env.ib**

Prompt the user for their `TWS_USERNAME` and `TWS_PASSWORD`. Create `packages/runner/.env.ib` with their values.

- [ ] **Step 3: Add .env.ib to .gitignore**

Append to the project root `.gitignore`:

```
# Interactive Brokers credentials
.env.ib
```

- [ ] **Step 4: Create data directory with .gitkeep**

```bash
mkdir -p data
touch data/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add packages/runner/.env.ib.example .gitignore data/.gitkeep
git commit -m "feat(runner): add IB credentials template and data directory"
```

---

### Task 3: Create Interactive Brokers data pull notebook

**Files:**
- Create: `packages/runner/runner/ib_data_pull.ipynb`

This is the main deliverable. The notebook has these sections:

1. **Setup & Connection** — Load env vars, start DockerizedIBGateway, connect HistoricInteractiveBrokersClient
2. **Instrument Discovery** — Request instrument details from IB
3. **Data Pull** — Pull historical bars with configurable instrument/timeframe/date range
4. **Save to CSV** — Save in the format expected by BarDataWrangler (columns: timestamp, open, high, low, close, volume)
5. **Cleanup** — Stop gateway container

- [ ] **Step 1: Create the notebook with all cells**

The notebook should contain these cells:

**Cell 1 (Markdown):**
```markdown
# Interactive Brokers — Historical Data Pull

Connect to IB via DockerizedIBGateway and pull historical bar data.
Saves to CSV format compatible with NautilusTrader's `BarDataWrangler`.

## Prerequisites
- Docker Desktop running
- `.env.ib` file with `TWS_USERNAME` and `TWS_PASSWORD`
- IB account with market data subscriptions
```

**Cell 2 (Code) — Imports and env loading:**
```python
import asyncio
import datetime
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from nautilus_trader.adapters.interactive_brokers.common import IBContract
from nautilus_trader.adapters.interactive_brokers.config import DockerizedIBGatewayConfig
from nautilus_trader.adapters.interactive_brokers.gateway import DockerizedIBGateway
from nautilus_trader.adapters.interactive_brokers.historical.client import (
    HistoricInteractiveBrokersClient,
)

# Load IB credentials from .env.ib
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.ib" if "__file__" in dir() else ".env.ib")

DATA_DIR = Path("../../../data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

print(f"TWS_USERNAME: {'set' if os.getenv('TWS_USERNAME') else 'NOT SET'}")
print(f"TWS_PASSWORD: {'set' if os.getenv('TWS_PASSWORD') else 'NOT SET'}")
print(f"Data directory: {DATA_DIR.resolve()}")
```

**Cell 3 (Markdown):**
```markdown
## 1. Start IB Gateway (Docker)

This starts a containerized IB Gateway. It uses your `.env.ib` credentials.
The container exposes port 4001 (live) for API connections.

> **Note:** First run will pull the Docker image (~1.5 GB). Subsequent starts are fast.
> The gateway takes ~30-60 seconds to fully authenticate.
```

**Cell 4 (Code) — Start gateway:**
```python
gateway_config = DockerizedIBGatewayConfig(
    username=os.getenv("TWS_USERNAME"),
    password=os.getenv("TWS_PASSWORD"),
    trading_mode="live",
    read_only_api=True,
    timeout=300,
)

gateway = DockerizedIBGateway(config=gateway_config)
gateway.safe_start()
print(f"Gateway running on {gateway.host}:{gateway.port}")
```

**Cell 5 (Markdown):**
```markdown
## 2. Connect Historical Data Client

Connects to the running IB Gateway for historical data requests.
```

**Cell 6 (Code) — Connect client:**
```python
client = HistoricInteractiveBrokersClient(
    host=gateway.host,
    port=gateway.port,
    client_id=1,
)

await client.connect()
print("Connected to IB Gateway")
```

**Cell 7 (Markdown):**
```markdown
## 3. Pull Historical Data

Configure the instrument, bar size, and date range below.
Two examples are provided: XAUUSD 1-minute and 5-minute bars.

### IB Rate Limits
- Max 60 requests per 10 minutes
- No identical requests within 15 seconds
- The client handles chunked requests automatically

### Available Bar Specifications
- `1-MINUTE-BID`, `1-MINUTE-LAST`, `1-MINUTE-MID`
- `5-MINUTE-BID`, `5-MINUTE-LAST`, `5-MINUTE-MID`
- `1-HOUR-BID`, `1-HOUR-LAST`, `1-HOUR-MID`
- `1-DAY-BID`, `1-DAY-LAST`, `1-DAY-MID`
```

**Cell 8 (Code) — Define XAUUSD contract:**
```python
# XAUUSD (Spot Gold) — available for non-US residents
# For US residents, use: IBContract(secType="FUT", symbol="GC", exchange="COMEX", lastTradeDateOrContractMonth="YYYYMM")
xauusd_contract = IBContract(
    secType="CFD",
    symbol="XAUUSD",
    exchange="SMART",
    currency="USD",
)

# Date range — adjust as needed
# IB provides up to ~5 years of 1-minute data
end_date = datetime.datetime.now()
start_date = end_date - datetime.timedelta(days=365)  # 1 year

print(f"Contract: {xauusd_contract.symbol}")
print(f"Date range: {start_date.date()} to {end_date.date()}")
```

**Cell 9 (Markdown):**
```markdown
### Example 1: Pull 1-Minute Bars
```

**Cell 10 (Code) — Pull 1-min bars:**
```python
bars_1m = await client.request_bars(
    bar_specifications=["1-MINUTE-BID"],
    start_date_time=start_date,
    end_date_time=end_date,
    tz_name="UTC",
    contracts=[xauusd_contract],
    use_rth=False,  # Include extended hours for forex/CFDs
    timeout=120,
)

print(f"Received {len(bars_1m)} 1-minute bars")
if bars_1m:
    print(f"First bar: {bars_1m[0]}")
    print(f"Last bar:  {bars_1m[-1]}")
```

**Cell 11 (Code) — Save 1-min to CSV:**
```python
if bars_1m:
    df_1m = pd.DataFrame([
        {
            "timestamp": pd.Timestamp(bar.ts_event, unit="ns", tz="UTC"),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in bars_1m
    ])

    filepath_1m = DATA_DIR / "xauusd_1m.csv"
    df_1m.to_csv(filepath_1m, index=False)
    print(f"Saved {len(df_1m)} bars to {filepath_1m.resolve()}")
    df_1m.head()
```

**Cell 12 (Markdown):**
```markdown
### Example 2: Pull 5-Minute Bars
```

**Cell 13 (Code) — Pull 5-min bars:**
```python
bars_5m = await client.request_bars(
    bar_specifications=["5-MINUTE-BID"],
    start_date_time=start_date,
    end_date_time=end_date,
    tz_name="UTC",
    contracts=[xauusd_contract],
    use_rth=False,
    timeout=120,
)

print(f"Received {len(bars_5m)} 5-minute bars")
if bars_5m:
    print(f"First bar: {bars_5m[0]}")
    print(f"Last bar:  {bars_5m[-1]}")
```

**Cell 14 (Code) — Save 5-min to CSV:**
```python
if bars_5m:
    df_5m = pd.DataFrame([
        {
            "timestamp": pd.Timestamp(bar.ts_event, unit="ns", tz="UTC"),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in bars_5m
    ])

    filepath_5m = DATA_DIR / "xauusd_5m.csv"
    df_5m.to_csv(filepath_5m, index=False)
    print(f"Saved {len(df_5m)} bars to {filepath_5m.resolve()}")
    df_5m.head()
```

**Cell 15 (Markdown):**
```markdown
### Custom Pull

Modify the contract, bar spec, and date range below to pull any instrument.
```

**Cell 16 (Code) — Custom pull template:**
```python
# === CONFIGURE YOUR PULL HERE ===
custom_contract = IBContract(
    secType="CFD",       # STK, FUT, OPT, CFD, CASH
    symbol="XAUUSD",     # IB symbol
    exchange="SMART",    # Exchange
    currency="USD",      # Currency
)

custom_bar_specs = ["1-MINUTE-BID"]  # Change timeframe here
custom_start = datetime.datetime.now() - datetime.timedelta(days=30)  # 30 days
custom_end = datetime.datetime.now()
custom_filename = "custom_data.csv"
# ================================

custom_bars = await client.request_bars(
    bar_specifications=custom_bar_specs,
    start_date_time=custom_start,
    end_date_time=custom_end,
    tz_name="UTC",
    contracts=[custom_contract],
    use_rth=False,
    timeout=120,
)

print(f"Received {len(custom_bars)} bars")

if custom_bars:
    df_custom = pd.DataFrame([
        {
            "timestamp": pd.Timestamp(bar.ts_event, unit="ns", tz="UTC"),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in custom_bars
    ])

    filepath_custom = DATA_DIR / custom_filename
    df_custom.to_csv(filepath_custom, index=False)
    print(f"Saved {len(df_custom)} bars to {filepath_custom.resolve()}")
    df_custom.head()
```

**Cell 17 (Markdown):**
```markdown
## 4. Cleanup

Stop the IB Gateway Docker container when done.
```

**Cell 18 (Code) — Stop gateway:**
```python
gateway.safe_stop()
print("IB Gateway stopped")
```

- [ ] **Step 2: Add python-dotenv to dependencies**

Add `python-dotenv>=1.0.0` to the `dependencies` list in `packages/runner/pyproject.toml` and run `uv sync --all-extras`.

- [ ] **Step 3: Install Jupyter kernel for the runner venv**

```bash
cd packages/runner
uv run python -m ipykernel install --user --name nautilus-runner --display-name "Nautilus Runner (3.13)"
```

- [ ] **Step 4: Commit**

```bash
git add packages/runner/runner/ib_data_pull.ipynb packages/runner/pyproject.toml packages/runner/uv.lock
git commit -m "feat(runner): add IB historical data pull notebook"
```

---

### Task 4: Validate end-to-end data pull

This task requires the user to have Docker Desktop running and valid IB credentials.

- [ ] **Step 1: Ensure Docker Desktop is running**

```bash
docker info > /dev/null 2>&1 && echo "Docker OK" || echo "Docker NOT running"
```

- [ ] **Step 2: Ask user to confirm IB credentials are in .env.ib**

Prompt the user to verify their `.env.ib` file has correct `TWS_USERNAME` and `TWS_PASSWORD`.

- [ ] **Step 3: Run the notebook cells sequentially**

Open the notebook in Jupyter and run cells 1-14 (through 5-min save). Verify:
- Gateway container starts successfully
- Client connects to IB
- 1-minute bars are pulled and saved to `data/xauusd_1m.csv`
- 5-minute bars are pulled and saved to `data/xauusd_5m.csv`

- [ ] **Step 4: Verify CSV format is compatible with backtest**

```python
import pandas as pd
df = pd.read_csv("data/xauusd_5m.csv", parse_dates=["timestamp"])
df = df.set_index("timestamp")
df.index = pd.to_datetime(df.index, utc=True)
print(df.columns.tolist())  # Should be: ['open', 'high', 'low', 'close', 'volume']
print(df.dtypes)
print(df.head())
```

- [ ] **Step 5: Stop gateway and commit**

Run cell 18 to stop the gateway container, then:

```bash
git add -A
git commit -m "feat(runner): validate IB data pull end-to-end"
```

---

### Task 5: Dashboard validation (optional)

If the user wants to verify the pulled data works with the existing dashboard:

- [ ] **Step 1: Start backend and frontend on worktree ports**

Use non-default ports to avoid conflicts with any running main instance:

```bash
NAUTILUS_PORT=8001 VITE_PORT=5174 VITE_API_URL=http://localhost:8001 bun run dev
```

- [ ] **Step 2: Run the BBB backtest with the pulled data**

The BBB notebook at `packages/runner/runner/bbb_backtest.ipynb` reads from `data/xauusd_5m.csv`. After pulling data via the IB notebook, run the BBB backtest to generate feather files in the catalog.

- [ ] **Step 3: Verify results appear in dashboard**

Open `http://localhost:5174` and confirm the new backtest run appears with XAUUSD data.
