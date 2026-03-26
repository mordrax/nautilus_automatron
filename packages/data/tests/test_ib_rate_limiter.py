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
