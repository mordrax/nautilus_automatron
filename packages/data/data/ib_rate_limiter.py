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
