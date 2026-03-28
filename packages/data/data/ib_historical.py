"""Shared utilities for pulling historical data from Interactive Brokers.

Provides rate limiting, chunked downloading, data validation, and catalog
writing — used by all IB data pull notebooks.

Usage:
    from data.ib_historical import (
        RateLimiter, pull_bars, save_bars_to_catalog,
        check_tws_connection, connect_client,
    )
"""

import asyncio
import datetime
import json
import os
import socket
import subprocess
import time
import uuid
from collections import deque
from pathlib import Path

import pyarrow.ipc as ipc

from nautilus_trader.adapters.interactive_brokers.common import IBContract
from nautilus_trader.adapters.interactive_brokers.historical.client import (
    HistoricInteractiveBrokersClient,
)
from nautilus_trader.core.nautilus_pyo3.model import Bar as PyO3Bar
from nautilus_trader.serialization.arrow.serializer import ArrowSerializer


# === IB Rate Limits ===
# Max duration per single reqHistoricalData call, keyed by bar size in seconds.
# Value is (timedelta for chunking, IB duration string for the API call).
MAX_CHUNK = {
    5:     (datetime.timedelta(hours=1),   "3600 S"),
    10:    (datetime.timedelta(hours=4),   "14400 S"),
    15:    (datetime.timedelta(hours=4),   "14400 S"),
    30:    (datetime.timedelta(hours=8),   "28800 S"),
    60:    (datetime.timedelta(days=1),    "1 D"),
    120:   (datetime.timedelta(days=2),    "2 D"),
    180:   (datetime.timedelta(weeks=1),   "1 W"),
    300:   (datetime.timedelta(weeks=1),   "1 W"),
    600:   (datetime.timedelta(weeks=1),   "1 W"),
    900:   (datetime.timedelta(weeks=1),   "1 W"),
    1200:  (datetime.timedelta(weeks=1),   "1 W"),
    1800:  (datetime.timedelta(weeks=1),   "1 W"),
    3600:  (datetime.timedelta(days=30),   "1 M"),
    86400: (datetime.timedelta(days=365),  "1 Y"),
}

BAR_SPEC_TO_SECONDS = {
    "5-SECOND": 5, "10-SECOND": 10, "15-SECOND": 15, "30-SECOND": 30,
    "1-MINUTE": 60, "2-MINUTE": 120, "3-MINUTE": 180, "5-MINUTE": 300,
    "10-MINUTE": 600, "15-MINUTE": 900, "20-MINUTE": 1200, "30-MINUTE": 1800,
    "1-HOUR": 3600, "1-DAY": 86400,
}

# IB pacing: max 60 requests per 600 seconds, max 6 per 2 seconds
MAX_REQUESTS_PER_WINDOW = 55  # conservative (under 60)
WINDOW_SECONDS = 600
MIN_DELAY_BETWEEN_REQUESTS = 3.0  # 1 request every 3 seconds


def parse_bar_seconds(bar_spec: str) -> int:
    """Parse '1-MINUTE-MID' -> 60 (seconds for the size-timeframe part)."""
    parts = bar_spec.rsplit("-", 1)  # split off price type
    size_tf = parts[0]  # e.g. '1-MINUTE'
    if size_tf not in BAR_SPEC_TO_SECONDS:
        raise ValueError(
            f"Unknown bar specification: {bar_spec}. "
            f"Known: {list(BAR_SPEC_TO_SECONDS.keys())}"
        )
    return BAR_SPEC_TO_SECONDS[size_tf]


def chunk_date_range(
    start: datetime.datetime,
    end: datetime.datetime,
    chunk_size: datetime.timedelta,
):
    """Yield (chunk_start, chunk_end) pairs walking backward from end to start.

    Walks backward because IB's reqHistoricalData uses end_date + duration.
    """
    current_end = end
    while current_end > start:
        chunk_start = max(current_end - chunk_size, start)
        yield chunk_start, current_end
        current_end = chunk_start


class RateLimiter:
    """Tracks request timestamps and enforces IB pacing rules."""

    def __init__(
        self,
        max_requests: int = MAX_REQUESTS_PER_WINDOW,
        window: int = WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window = window
        self.timestamps: deque[float] = deque()

    def _prune(self):
        now = time.monotonic()
        while self.timestamps and (now - self.timestamps[0]) > self.window:
            self.timestamps.popleft()

    async def acquire(self):
        """Wait until a request slot is available, then record it."""
        while True:
            self._prune()
            if len(self.timestamps) < self.max_requests:
                break
            wait = self.window - (time.monotonic() - self.timestamps[0]) + 0.5
            print(
                f"  [rate] Pacing: {len(self.timestamps)}/{self.max_requests} "
                f"requests in window. Waiting {wait:.0f}s..."
            )
            await asyncio.sleep(wait)

        if self.timestamps:
            elapsed = time.monotonic() - self.timestamps[-1]
            if elapsed < MIN_DELAY_BETWEEN_REQUESTS:
                await asyncio.sleep(MIN_DELAY_BETWEEN_REQUESTS - elapsed)

        self.timestamps.append(time.monotonic())

    @property
    def remaining(self) -> int:
        self._prune()
        return self.max_requests - len(self.timestamps)


def check_tws_connection(host: str, port: int) -> bool:
    """Check if TWS is accepting connections on the given host:port."""
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def kill_stale_ib_connections(current_pid: int, tws_port: int = 7496):
    """Find and kill orphaned Python processes holding IB connections."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{tws_port}", "-P"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[0].lower() == "python":
                pid = int(parts[1])
                if pid != current_pid:
                    print(f"  Killing stale process PID={pid}")
                    subprocess.run(["kill", str(pid)], timeout=5)
    except Exception:
        pass


async def connect_client(
    host: str = "127.0.0.1",
    port: int = 7496,
    client_id: int = 1,
) -> HistoricInteractiveBrokersClient:
    """Connect to TWS with connection check and stale process cleanup.

    Raises ConnectionError if TWS is not reachable.
    """
    if not check_tws_connection(host, port):
        raise ConnectionError(
            f"Cannot connect to TWS at {host}:{port}. "
            f"Ensure TWS is running with API enabled."
        )

    kill_stale_ib_connections(os.getpid(), port)

    client = HistoricInteractiveBrokersClient(
        host=host, port=port, client_id=client_id,
    )
    await client.connect()
    await asyncio.sleep(2)  # Wait for IB readiness
    print(f"Connected to TWS at {host}:{port} (client_id={client_id})")
    return client


def validate_bars(bars, chunk_start, chunk_end):
    """Validate returned bars. Returns (valid_bars, issues)."""
    if not bars:
        return [], []
    issues = []

    tolerance = datetime.timedelta(days=1)
    first_ts = bars[0].ts_event
    last_ts = bars[-1].ts_event

    expected_start_ns = int(
        (chunk_start - tolerance)
        .replace(tzinfo=datetime.timezone.utc)
        .timestamp()
        * 1e9
    )
    expected_end_ns = int(
        (chunk_end + tolerance)
        .replace(tzinfo=datetime.timezone.utc)
        .timestamp()
        * 1e9
    )

    if first_ts < expected_start_ns:
        issues.append("first bar timestamp before expected range")
    if last_ts > expected_end_ns:
        issues.append("last bar timestamp after expected range")

    bad_prices = sum(
        1 for b in bars if float(b.open) <= 0 or float(b.close) <= 0
    )
    if bad_prices > 0:
        issues.append(f"{bad_prices} bars with zero/negative prices")

    return bars, issues


async def pull_bars(
    client: HistoricInteractiveBrokersClient,
    contract: IBContract,
    bar_spec: str,
    start: datetime.datetime,
    end: datetime.datetime,
    rate_limiter: RateLimiter,
    use_rth: bool = False,
    timeout_per_chunk: int = 10,
    max_retries: int = 3,
    retry_delay: float = 5.0,
) -> list:
    """Pull historical bars with rate limiting, retries, and data validation.

    Splits the date range into chunks based on IB's max duration per bar size,
    paces requests to stay within IB's rate limits, retries on failure, and
    validates each chunk's data.

    Returns deduplicated, sorted list of Bar objects.
    """
    bar_seconds = parse_bar_seconds(bar_spec)
    chunk_td, duration_str = MAX_CHUNK[bar_seconds]

    chunks = list(chunk_date_range(start, end, chunk_td))
    total_chunks = len(chunks)

    print(f"[pull] {contract.symbol} {bar_spec}")
    print(
        f"[pull] Range: {start.date()} to {end.date()} "
        f"({(end - start).days} days)"
    )
    print(
        f"[pull] Chunk size: {chunk_td} (duration: {duration_str}), "
        f"{total_chunks} requests needed"
    )
    print(
        f"[pull] Rate limiter: {rate_limiter.remaining} requests "
        f"remaining in window"
    )
    if total_chunks > rate_limiter.remaining:
        est_pauses = (
            (total_chunks - rate_limiter.remaining) // MAX_REQUESTS_PER_WINDOW
        )
        print(
            f"[pull] NOTE: Will need to pause for rate limiting "
            f"(~{est_pauses * 10} min of waiting)"
        )
    print()

    # Ensure instrument is loaded (required before requesting bars)
    try:
        await client.request_instruments(contracts=[contract])
    except Exception:
        pass  # may already be cached

    all_bars = []
    failed_chunks = []
    t0 = time.perf_counter()

    for i, (chunk_start, chunk_end) in enumerate(chunks):
        # Adjust duration for partial chunks (last chunk may be shorter)
        actual_td = chunk_end - chunk_start
        if actual_td < chunk_td:
            total_secs = int(actual_td.total_seconds())
            if total_secs >= 86400:
                chunk_duration = f"{total_secs // 86400} D"
            else:
                chunk_duration = f"{max(30, total_secs)} S"
        else:
            chunk_duration = duration_str

        bars = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            await rate_limiter.acquire()

            elapsed = time.perf_counter() - t0
            retry_label = (
                f" (retry {attempt}/{max_retries})" if attempt > 1 else ""
            )
            print(
                f"  [{i + 1}/{total_chunks}] "
                f"{chunk_start.date()} to {chunk_end.date()} "
                f"dur={chunk_duration} slots={rate_limiter.remaining} "
                f"t={elapsed:.0f}s{retry_label}"
            )

            try:
                bars = await asyncio.wait_for(
                    client.request_bars(
                        bar_specifications=[bar_spec],
                        end_date_time=chunk_end,
                        duration=chunk_duration,
                        tz_name="UTC",
                        contracts=[contract],
                        use_rth=use_rth,
                        timeout=timeout_per_chunk,
                    ),
                    timeout=timeout_per_chunk + 5,
                )

                if bars:
                    valid_bars, issues = validate_bars(
                        bars, chunk_start, chunk_end
                    )
                    if issues:
                        print(
                            f"         -> {len(bars)} bars "
                            f"(WARNINGS: {'; '.join(issues)})"
                        )
                    else:
                        print(f"         -> {len(bars)} bars")
                    all_bars.extend(valid_bars)
                    break
                else:
                    print("         -> 0 bars (empty response)")
                    break  # empty is OK (weekend/holiday)

            except (asyncio.TimeoutError, asyncio.CancelledError):
                last_error = "timeout"
                print(f"         -> TIMEOUT after {timeout_per_chunk}s")
                if attempt < max_retries:
                    wait = retry_delay * attempt
                    print(f"         Retrying in {wait:.0f}s...")
                    await asyncio.sleep(wait)
            except Exception as e:
                last_error = str(e)
                print(f"         -> ERROR: {e}")
                if attempt < max_retries:
                    wait = retry_delay * attempt
                    print(f"         Retrying in {wait:.0f}s...")
                    await asyncio.sleep(wait)

        if bars is None and last_error:
            failed_chunks.append(
                (chunk_start.date(), chunk_end.date(), last_error)
            )
            print(
                f"         GIVING UP on this chunk after "
                f"{max_retries} attempts"
            )

    total_time = time.perf_counter() - t0
    print()
    print(f"[pull] Done: {len(all_bars)} total bars in {total_time:.1f}s")

    if failed_chunks:
        print(f"[pull] FAILED CHUNKS ({len(failed_chunks)}):")
        for cs, ce, err in failed_chunks:
            print(f"  {cs} to {ce}: {err}")

    # Sort by market timestamp and deduplicate
    if all_bars:
        all_bars.sort(key=lambda b: b.ts_event)
        seen: set[int] = set()
        deduped = []
        for bar in all_bars:
            if bar.ts_event not in seen:
                seen.add(bar.ts_event)
                deduped.append(bar)
        if len(deduped) < len(all_bars):
            print(
                f"[pull] Removed {len(all_bars) - len(deduped)} "
                f"duplicate bars"
            )
        all_bars = deduped

    return all_bars


def save_bars_to_catalog(
    bars: list,
    catalog_path: Path,
    run_id: str | None = None,
) -> str:
    """Save bars to the NautilusTrader streaming catalog format.

    Creates the directory structure:
        catalog_path/backtest/{run_id}/
            config.json
            bar/{bar_type}/{bar_type}_{ts_ns}.feather

    Returns the run_id used.
    """
    t0 = time.perf_counter()

    if not bars:
        print("WARNING: No bars to save — skipping")
        return ""

    bar_count = len(bars)
    bar_type_str = str(bars[0].bar_type)
    print(f"[save] {bar_count} bars of type {bar_type_str}")

    if not catalog_path.exists():
        catalog_path.mkdir(parents=True, exist_ok=True)

    run_id = run_id or str(uuid.uuid4())
    run_dir = catalog_path / "backtest" / run_id
    print(f"[save] Run ID: {run_id}")

    # Convert Cython bars to PyO3 bars
    from nautilus_trader.model.data import Bar as CythonBar

    print(f"[save] Serializing {bar_count} bars to Arrow format...")
    t1 = time.perf_counter()
    if bars and isinstance(bars[0], CythonBar):
        pyo3_bars = CythonBar.to_pyo3_list(bars)
    else:
        pyo3_bars = bars
    batch = ArrowSerializer.rust_defined_to_record_batch(
        pyo3_bars, data_cls=PyO3Bar
    )
    t2 = time.perf_counter()
    print(
        f"[save] Serialized in {t2 - t1:.2f}s — "
        f"{batch.num_rows} rows, {batch.nbytes / 1024:.1f} KB"
    )

    # Create bar directory (replace filesystem-unsafe characters)
    safe_bar_type = bar_type_str.replace("/", "-").replace(":", "-")
    bar_dir = run_dir / "bar" / safe_bar_type
    bar_dir.mkdir(parents=True, exist_ok=True)

    # Write feather file
    ts_ns = bars[0].ts_event
    feather_path = bar_dir / f"{safe_bar_type}_{ts_ns}.feather"

    if feather_path.exists():
        print(f"[save] WARNING: Overwriting existing file: {feather_path.name}")

    print(f"[save] Writing feather file: {feather_path.name}")
    t3 = time.perf_counter()
    with open(feather_path, "wb") as f:
        writer = ipc.new_stream(f, batch.schema)
        writer.write_table(batch)
        writer.close()
    t4 = time.perf_counter()
    file_size = feather_path.stat().st_size
    print(
        f"[save] Written in {t4 - t3:.2f}s — "
        f"{file_size / 1024:.1f} KB on disk"
    )

    # Write minimal config.json
    config_path = run_dir / "config.json"
    if not config_path.exists():
        config = {
            "environment": "backtest",
            "trader_id": "BACKTESTER-001",
            "instance_id": None,
        }
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print("[save] Created config.json")

    total = time.perf_counter() - t0
    print(
        f"[save] Done in {total:.2f}s — "
        f"{bar_dir.relative_to(catalog_path)}"
    )

    return run_id
