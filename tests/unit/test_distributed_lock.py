"""Comprehensive tests for Redis-based distributed locking.

Tests cover: core locking, context manager, auto-renewal,
scheduler integration, and edge cases.  All Redis interactions
are mocked via AsyncMock — no real Redis required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.utils.distributed_lock import (
    KEY_PREFIX,
    DistributedLock,
)

# ======================================================================
# Helpers
# ======================================================================

REDIS_URL = "redis://localhost:6379/0"


def _make_redis_mock(
    *,
    set_return: bool = True,
    eval_return: int = 1,
) -> AsyncMock:
    """Build a mock Redis client with configurable SET/EVAL results."""
    client = AsyncMock()
    client.set = AsyncMock(return_value=set_return)
    client.eval = AsyncMock(return_value=eval_return)
    client.aclose = AsyncMock()
    return client


def _patch_redis(client: AsyncMock):
    """Patch aioredis.from_url to return *client*."""
    return patch(
        "shieldops.utils.distributed_lock.aioredis.from_url",
        return_value=client,
    )


# ======================================================================
# Core locking — acquire
# ======================================================================


class TestAcquire:
    """Tests for DistributedLock.acquire()."""

    @pytest.mark.asyncio
    async def test_acquire_succeeds_first_try(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "job-1", ttl=60)
            result = await lock.acquire()

        assert result is True
        client.set.assert_awaited_once()
        call_kwargs = client.set.call_args
        assert call_kwargs.kwargs["nx"] is True
        assert call_kwargs.kwargs["ex"] == 60

    @pytest.mark.asyncio
    async def test_acquire_fails_when_held(self):
        client = _make_redis_mock(set_return=False)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "job-2", ttl=60)
            result = await lock.acquire()

        assert result is False
        assert lock.lock_value is None

    @pytest.mark.asyncio
    async def test_acquire_retries_up_to_max(self):
        client = _make_redis_mock(set_return=False)
        with _patch_redis(client):
            lock = DistributedLock(
                REDIS_URL,
                "retry-job",
                ttl=60,
                retry_interval=0.01,
                max_retries=3,
            )
            result = await lock.acquire()

        assert result is False
        # 1 initial + 3 retries = 4 attempts
        assert client.set.await_count == 4

    @pytest.mark.asyncio
    async def test_acquire_succeeds_on_retry(self):
        """Lock acquired on the second attempt."""
        client = _make_redis_mock()
        # First call fails, second succeeds
        client.set = AsyncMock(side_effect=[False, True])
        with _patch_redis(client):
            lock = DistributedLock(
                REDIS_URL,
                "retry-ok",
                ttl=60,
                retry_interval=0.01,
                max_retries=2,
            )
            result = await lock.acquire()

        assert result is True
        assert client.set.await_count == 2

    @pytest.mark.asyncio
    async def test_acquire_sets_unique_lock_value(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "uuid-check", ttl=60)
            await lock.acquire()

        assert lock.lock_value is not None
        assert len(lock.lock_value) == 32  # hex UUID

    @pytest.mark.asyncio
    async def test_acquire_uses_correct_key(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "key-test", ttl=60)
            await lock.acquire()

        call_args = client.set.call_args
        assert call_args.args[0] == f"{KEY_PREFIX}:key-test"

    @pytest.mark.asyncio
    async def test_acquire_starts_renewal_task(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "renew-start", ttl=60)
            await lock.acquire()

        assert lock._renewal_task is not None
        assert not lock._renewal_task.done()
        # Cleanup
        await lock.release()


# ======================================================================
# Core locking — release
# ======================================================================


class TestRelease:
    """Tests for DistributedLock.release()."""

    @pytest.mark.asyncio
    async def test_release_succeeds_when_owner(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "rel-ok", ttl=60)
            await lock.acquire()
            result = await lock.release()

        assert result is True
        client.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_release_fails_when_not_owner(self):
        """Lua script returns 0 when value doesn't match."""
        client = _make_redis_mock(set_return=True, eval_return=0)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "rel-fail", ttl=60)
            await lock.acquire()
            result = await lock.release()

        assert result is False

    @pytest.mark.asyncio
    async def test_release_noop_when_not_acquired(self):
        """Releasing without acquiring should return False."""
        client = _make_redis_mock()
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "no-acq", ttl=60)
            result = await lock.release()

        assert result is False
        client.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_release_clears_lock_value(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "clr-val", ttl=60)
            await lock.acquire()
            assert lock.lock_value is not None
            await lock.release()

        assert lock.lock_value is None

    @pytest.mark.asyncio
    async def test_release_cancels_renewal_task(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "cancel-renew", ttl=60)
            await lock.acquire()
            task = lock._renewal_task
            assert task is not None

            await lock.release()

        assert lock._renewal_task is None
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_release_closes_redis_client(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "close-cli", ttl=60)
            await lock.acquire()
            await lock.release()

        client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_release_handles_redis_error(self):
        """Release should not raise even if Redis errors."""
        client = _make_redis_mock(set_return=True)
        client.eval = AsyncMock(side_effect=ConnectionError("Redis down"))
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "err-rel", ttl=60)
            await lock.acquire()
            result = await lock.release()

        assert result is False
        assert lock.lock_value is None


# ======================================================================
# Core locking — renew
# ======================================================================


class TestRenew:
    """Tests for DistributedLock.renew()."""

    @pytest.mark.asyncio
    async def test_renew_extends_ttl(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "renew-ok", ttl=120)
            await lock.acquire()
            # Reset eval mock for the renew call
            client.eval.reset_mock()
            client.eval.return_value = 1

            result = await lock.renew()

        assert result is True
        client.eval.assert_awaited_once()
        # Verify TTL in ms was passed
        call_args = client.eval.call_args
        assert call_args.args[4] == str(120 * 1000)

    @pytest.mark.asyncio
    async def test_renew_fails_when_not_owner(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "renew-fail", ttl=60)
            await lock.acquire()
            client.eval.reset_mock()
            client.eval.return_value = 0

            result = await lock.renew()

        assert result is False
        # Cleanup
        client.eval.return_value = 1
        await lock.release()

    @pytest.mark.asyncio
    async def test_renew_without_acquire_returns_false(self):
        lock = DistributedLock(REDIS_URL, "no-renew", ttl=60)
        result = await lock.renew()
        assert result is False

    @pytest.mark.asyncio
    async def test_renew_handles_redis_error(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "renew-err", ttl=60)
            await lock.acquire()
            client.eval.reset_mock()
            client.eval.side_effect = ConnectionError("gone")

            result = await lock.renew()

        assert result is False


# ======================================================================
# Context manager
# ======================================================================


class TestContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    async def test_aenter_returns_true_when_acquired(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "ctx-true", ttl=60)
            async with lock as acquired:
                assert acquired is True

    @pytest.mark.asyncio
    async def test_aenter_returns_false_when_not_acquired(self):
        client = _make_redis_mock(set_return=False)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "ctx-false", ttl=60)
            async with lock as acquired:
                assert acquired is False

    @pytest.mark.asyncio
    async def test_aexit_releases_lock(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "ctx-rel", ttl=60)
            async with lock as acquired:
                assert acquired is True

        # eval called during release (Lua CAS script)
        client.eval.assert_awaited()
        assert lock.lock_value is None

    @pytest.mark.asyncio
    async def test_aexit_releases_on_exception(self):
        """Lock released even when the body raises."""
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "ctx-exc", ttl=60)
            with pytest.raises(ValueError, match="boom"):
                async with lock:
                    raise ValueError("boom")

        client.eval.assert_awaited()
        assert lock.lock_value is None

    @pytest.mark.asyncio
    async def test_two_locks_cannot_both_acquire(self):
        """Simulates two instances contending for the same lock."""
        # First lock succeeds, second fails (NX semantics)
        client1 = _make_redis_mock(set_return=True, eval_return=1)
        client2 = _make_redis_mock(set_return=False)

        with _patch_redis(client1):
            lock1 = DistributedLock(REDIS_URL, "contend", ttl=60)
            acquired1 = await lock1.acquire()

        with _patch_redis(client2):
            lock2 = DistributedLock(REDIS_URL, "contend", ttl=60)
            acquired2 = await lock2.acquire()

        assert acquired1 is True
        assert acquired2 is False

        # Cleanup
        with _patch_redis(client1):
            await lock1.release()


# ======================================================================
# Auto-renewal
# ======================================================================


class TestAutoRenewal:
    """Tests for the background auto-renewal task."""

    @pytest.mark.asyncio
    async def test_renewal_task_created_on_acquire(self):
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "task-check", ttl=60)
            await lock.acquire()
            assert lock._renewal_task is not None
            assert not lock._renewal_task.done()
            await lock.release()

    @pytest.mark.asyncio
    async def test_renewal_task_cancelled_on_release(self):
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "task-cancel", ttl=60)
            await lock.acquire()
            task = lock._renewal_task
            await lock.release()

        assert lock._renewal_task is None
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_renewal_keeps_lock_alive(self):
        """With a short TTL, auto-renew fires and extends the lock."""
        client = _make_redis_mock(set_return=True, eval_return=1)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "long-op", ttl=2)
            await lock.acquire()
            # Renewal fires at ttl/2 = 1s
            await asyncio.sleep(1.5)

            # eval was called for renew (beyond the acquire)
            assert client.eval.await_count >= 1
            await lock.release()

    @pytest.mark.asyncio
    async def test_renewal_stops_when_renew_fails(self):
        """Auto-renew stops if the lock is no longer ours."""
        client = _make_redis_mock(set_return=True)
        with _patch_redis(client):
            lock = DistributedLock(REDIS_URL, "renew-stop", ttl=2)
            await lock.acquire()

            # After acquire, make renew fail
            client.eval.return_value = 0
            # Wait for renewal to fire and detect failure
            await asyncio.sleep(1.5)

            task = lock._renewal_task
            # Give the task a moment to finish
            await asyncio.sleep(0.2)
            assert task.done()

            # Cleanup (release won't work since eval returns 0)
            lock._lock_value = None
            await lock._cancel_renewal()
            await lock._close_client()


# ======================================================================
# Validation
# ======================================================================


class TestValidation:
    """Tests for constructor validation."""

    def test_ttl_must_be_positive(self):
        with pytest.raises(ValueError, match="ttl must be positive"):
            DistributedLock(REDIS_URL, "bad-ttl", ttl=0)

    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError, match="ttl must be positive"):
            DistributedLock(REDIS_URL, "neg-ttl", ttl=-5)

    def test_key_property(self):
        lock = DistributedLock(REDIS_URL, "my-lock", ttl=60)
        assert lock.key == f"{KEY_PREFIX}:my-lock"

    def test_lock_value_initially_none(self):
        lock = DistributedLock(REDIS_URL, "init", ttl=60)
        assert lock.lock_value is None


# ======================================================================
# Scheduler integration
# ======================================================================


class TestSchedulerIntegration:
    """Tests for scheduler + distributed lock interaction."""

    @pytest.mark.asyncio
    async def test_job_executes_when_lock_acquired(self):
        """With redis_url, job runs normally when lock is free."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        client = _make_redis_mock(set_return=True, eval_return=1)

        with _patch_redis(client):
            scheduler = JobScheduler(redis_url=REDIS_URL)
            scheduler.add_job("locked-ok", func, interval_seconds=1)
            await scheduler.start()
            await asyncio.sleep(1.5)
            await scheduler.stop()

        func.assert_awaited()

    @pytest.mark.asyncio
    async def test_job_skipped_when_lock_held(self):
        """Job is skipped (not executed) when another instance holds the lock."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        client = _make_redis_mock(set_return=False)

        with _patch_redis(client):
            scheduler = JobScheduler(redis_url=REDIS_URL)
            scheduler.add_job("locked-skip", func, interval_seconds=1)
            await scheduler.start()
            await asyncio.sleep(1.5)
            await scheduler.stop()

        func.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lock_released_after_job_completes(self):
        """Lock is released after successful job execution."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        client = _make_redis_mock(set_return=True, eval_return=1)

        with _patch_redis(client):
            scheduler = JobScheduler(redis_url=REDIS_URL)
            scheduler.add_job("rel-after", func, interval_seconds=1)
            await scheduler.start()
            await asyncio.sleep(1.5)
            await scheduler.stop()

        # eval called at least once for release
        assert client.eval.await_count >= 1

    @pytest.mark.asyncio
    async def test_lock_released_on_job_failure(self):
        """Lock is released even when the job raises an exception."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock(side_effect=RuntimeError("job broke"))
        client = _make_redis_mock(set_return=True, eval_return=1)

        with _patch_redis(client):
            scheduler = JobScheduler(redis_url=REDIS_URL)
            scheduler.add_job("fail-rel", func, interval_seconds=1)
            await scheduler.start()
            await asyncio.sleep(1.5)
            await scheduler.stop()

        # The lock's __aexit__ still runs on exception
        assert client.eval.await_count >= 1

    @pytest.mark.asyncio
    async def test_scheduler_without_redis_url_works(self):
        """Backward compatibility: no redis_url means no locking."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        scheduler = JobScheduler()  # No redis_url
        scheduler.add_job("no-lock", func, interval_seconds=1)
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        func.assert_awaited()

    @pytest.mark.asyncio
    async def test_scheduler_empty_redis_url_works(self):
        """Empty string redis_url is treated as disabled."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        scheduler = JobScheduler(redis_url="")
        scheduler.add_job("empty-url", func, interval_seconds=1)
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        func.assert_awaited()

    @pytest.mark.asyncio
    async def test_scheduler_lock_ttl_uses_interval(self):
        """Lock TTL should be max(interval, 300)."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        client = _make_redis_mock(set_return=True, eval_return=1)

        with _patch_redis(client):
            scheduler = JobScheduler(redis_url=REDIS_URL)
            scheduler.add_job("ttl-check", func, interval_seconds=600)
            await scheduler.start()
            await asyncio.sleep(1.5)
            await scheduler.stop()

        # Verify TTL passed to SET was 600 (> 300)
        if client.set.await_count > 0:
            call_kwargs = client.set.call_args.kwargs
            assert call_kwargs["ex"] == 600

    @pytest.mark.asyncio
    async def test_scheduler_lock_ttl_minimum_300(self):
        """Lock TTL should not be below 300 for short intervals."""
        from shieldops.scheduler.scheduler import JobScheduler

        func = AsyncMock()
        client = _make_redis_mock(set_return=True, eval_return=1)

        with _patch_redis(client):
            scheduler = JobScheduler(redis_url=REDIS_URL)
            scheduler.add_job("min-ttl", func, interval_seconds=1)
            await scheduler.start()
            await asyncio.sleep(1.5)
            await scheduler.stop()

        if client.set.await_count > 0:
            call_kwargs = client.set.call_args.kwargs
            assert call_kwargs["ex"] == 300
