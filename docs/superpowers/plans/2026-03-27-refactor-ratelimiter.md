# Refactor RateLimiter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a new `packages/data` package, move `ib_data_pull.ipynb` into it, and extract the inline `RateLimiter` into a standalone IB rate limiter module with tests.

**Architecture:** Create `packages/data/` as a new Python package following the same structure as `packages/runner/`. The IB rate limiter lives at `packages/data/data/ib_rate_limiter.py` — it's IB-specific, so named accordingly. The notebook moves from `packages/runner/runner/ib_data_pull.ipynb` to `packages/data/data/ib_data_pull.ipynb` and imports the rate limiter from its sibling module.

**Tech Stack:** Python 3.12+, asyncio, pytest, collections.deque

**Branch:** Based on `interactive-brokers-integration` (where the notebook exists)

---

### Task 1: Create the `packages/data` package scaffold

**Files:**
- Create: `packages/data/pyproject.toml`
- Create: `packages/data/data/__init__.py`
- Create: `packages/data/tests/__init__.py`

- [ ] **Step 1: Create `packages/data/pyproject.toml`**

```toml
[project]
name = "nautilus-automatron-data"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = [
    "nautilus_trader",
    "nautilus-ibapi==10.43.2",
    "protobuf==5.29.5",
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
packages = ["data"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `packages/data/data/__init__.py`**

```python
"""Nautilus Automatron Data — data ingestion and IB integration."""
```

- [ ] **Step 3: Create `packages/data/tests/__init__.py`**

```python
```

(Empty file)

- [ ] **Step 4: Create the venv and install the package in dev mode**

```bash
cd packages/data && uv venv && uv pip install -e ".[dev]"
```

- [ ] **Step 5: Verify the package is importable**

```bash
cd packages/data && .venv/bin/python -c "import data; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add packages/data/pyproject.toml packages/data/data/__init__.py packages/data/tests/__init__.py
git commit -m "feat: create packages/data package scaffold"
```

---

### Task 2: Create IB rate limiter module with tests

**Files:**
- Create: `packages/data/data/ib_rate_limiter.py`
- Create: `packages/data/tests/test_ib_rate_limiter.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/data/tests/test_ib_rate_limiter.py`:

```python
"""Tests for the IB rate limiter module."""

import asyncio
import time

import pytest

from data.ib_rate_limiter import IBRateLimiter


class TestIBRateLimiterInit:
    def test_default_config(self):
        rl = IBRateLimiter()
        assert rl.max_requests == 55
        assert rl.window == 600

    def test_custom_config(self):
        rl = IBRateLimiter(max_requests=10, window=60, min_delay=1.0)
        assert rl.max_requests == 10
        assert rl.window == 60
        assert rl.remaining == 10


class TestRemaining:
    def test_remaining_starts_at_max(self):
        rl = IBRateLimiter(max_requests=5, window=60)
        assert rl.remaining == 5

    def test_remaining_decreases_after_acquire(self):
        rl = IBRateLimiter(max_requests=5, window=60, min_delay=0.0)
        asyncio.run(rl.acquire())
        assert rl.remaining == 4

    def test_remaining_recovers_after_window_expires(self):
        rl = IBRateLimiter(max_requests=5, window=1, min_delay=0.0)
        for _ in range(5):
            asyncio.run(rl.acquire())
        assert rl.remaining == 0
        time.sleep(1.1)
        assert rl.remaining == 5


class TestAcquire:
    def test_acquire_records_timestamp(self):
        rl = IBRateLimiter(max_requests=5, window=60, min_delay=0.0)
        asyncio.run(rl.acquire())
        assert len(rl.timestamps) == 1

    def test_acquire_multiple(self):
        rl = IBRateLimiter(max_requests=5, window=60, min_delay=0.0)
        for _ in range(3):
            asyncio.run(rl.acquire())
        assert len(rl.timestamps) == 3
        assert rl.remaining == 2

    def test_acquire_enforces_min_delay(self):
        rl = IBRateLimiter(max_requests=5, window=60, min_delay=0.1)
        t0 = time.monotonic()
        asyncio.run(rl.acquire())
        asyncio.run(rl.acquire())
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.1

    def test_acquire_waits_when_window_full(self):
        rl = IBRateLimiter(max_requests=2, window=1, min_delay=0.0)
        asyncio.run(rl.acquire())
        asyncio.run(rl.acquire())
        assert rl.remaining == 0
        t0 = time.monotonic()
        asyncio.run(rl.acquire())
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.8


class TestPrune:
    def test_prune_removes_expired_timestamps(self):
        rl = IBRateLimiter(max_requests=5, window=1, min_delay=0.0)
        asyncio.run(rl.acquire())
        asyncio.run(rl.acquire())
        assert len(rl.timestamps) == 2
        time.sleep(1.1)
        rl._prune()
        assert len(rl.timestamps) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/data && .venv/bin/python -m pytest tests/test_ib_rate_limiter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'data.ib_rate_limiter'`

- [ ] **Step 3: Create the IB rate limiter module**

Create `packages/data/data/ib_rate_limiter.py`:

```python
"""IB API rate limiter — sliding window with minimum inter-request delay.

Enforces Interactive Brokers pacing rules:
- Max requests per time window (default: 55 per 600s, conservative under IB's 60/600s limit)
- Minimum delay between consecutive requests (default: 3.0s)
"""

import asyncio
import time
from collections import deque

# IB pacing defaults: max 60 requests per 600 seconds, max 6 per 2 seconds.
# We use conservative values to avoid hitting the limits.
DEFAULT_MAX_REQUESTS = 55
DEFAULT_WINDOW_SECONDS = 600
DEFAULT_MIN_DELAY = 3.0


class IBRateLimiter:
    """Tracks request timestamps and enforces IB pacing rules.

    Uses a sliding window of timestamps to limit the total number of requests
    in a time window, plus a minimum delay between consecutive requests.
    """

    def __init__(
        self,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window: int = DEFAULT_WINDOW_SECONDS,
        min_delay: float = DEFAULT_MIN_DELAY,
    ):
        self.max_requests = max_requests
        self.window = window
        self.min_delay = min_delay
        self.timestamps: deque[float] = deque()

    def _prune(self) -> None:
        """Remove timestamps that have fallen outside the sliding window."""
        now = time.monotonic()
        while self.timestamps and (now - self.timestamps[0]) > self.window:
            self.timestamps.popleft()

    async def acquire(self) -> None:
        """Wait until a request slot is available, then record it."""
        while True:
            self._prune()
            if len(self.timestamps) < self.max_requests:
                break
            wait = self.window - (time.monotonic() - self.timestamps[0]) + 0.5
            print(
                f"  [rate] Pacing: {len(self.timestamps)}/{self.max_requests} requests in window. "
                f"Waiting {wait:.0f}s..."
            )
            await asyncio.sleep(wait)

        if self.timestamps:
            elapsed = time.monotonic() - self.timestamps[-1]
            if elapsed < self.min_delay:
                await asyncio.sleep(self.min_delay - elapsed)

        self.timestamps.append(time.monotonic())

    @property
    def remaining(self) -> int:
        """Number of request slots available in the current window."""
        self._prune()
        return self.max_requests - len(self.timestamps)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/data && .venv/bin/python -m pytest tests/test_ib_rate_limiter.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/data/data/ib_rate_limiter.py packages/data/tests/test_ib_rate_limiter.py
git commit -m "feat: add IBRateLimiter module with tests"
```

---

### Task 3: Move notebook to packages/data and update imports

**Files:**
- Move: `packages/runner/runner/ib_data_pull.ipynb` → `packages/data/data/ib_data_pull.ipynb`
- Modify: `packages/data/data/ib_data_pull.ipynb` (cell 3)

- [ ] **Step 1: Move the notebook**

```bash
git mv packages/runner/runner/ib_data_pull.ipynb packages/data/data/ib_data_pull.ipynb
```

- [ ] **Step 2: Update notebook imports and remove inline RateLimiter**

In cell 3 of `packages/data/data/ib_data_pull.ipynb`, make these changes:

**Add import** (after the existing imports):
```python
from data.ib_rate_limiter import IBRateLimiter
```

**Remove** these lines (the constants and inline class):
```python
# IB pacing: max 60 requests per 600 seconds, max 6 per 2 seconds
_MAX_REQUESTS_PER_WINDOW = 55  # conservative (under 60)
_WINDOW_SECONDS = 600
_MIN_DELAY_BETWEEN_REQUESTS = 3.0  # 1 request every 3 seconds
```

And the entire `class RateLimiter:` block (lines 186-222 in the original ipynb, from `class RateLimiter:` through the `remaining` property).

**Update** the global instance:
```python
# Old:
rate_limiter = RateLimiter()

# New:
rate_limiter = IBRateLimiter()
```

**Update** the `_MAX_REQUESTS_PER_WINDOW` reference in `pull_bars()`:
```python
# Old:
est_pauses = (total_chunks - rate_limiter.remaining) // _MAX_REQUESTS_PER_WINDOW

# New:
est_pauses = (total_chunks - rate_limiter.remaining) // rate_limiter.max_requests
```

**Remove `deque` from imports** if it's no longer used elsewhere in the cell. Keep `time` and `asyncio` — they're still used by `pull_bars()`.

- [ ] **Step 3: Verify the import works**

```bash
cd packages/data && .venv/bin/python -c "from data.ib_rate_limiter import IBRateLimiter; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 4: Run all data package tests**

```bash
cd packages/data && .venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/data/data/ib_data_pull.ipynb packages/runner/runner/ib_data_pull.ipynb
git commit -m "refactor: move ib_data_pull notebook to packages/data, use IBRateLimiter module"
```
