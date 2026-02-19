"""Async job scheduler -- runs periodic tasks using asyncio.

A lightweight alternative to APScheduler: each registered job gets its own
asyncio.Task that sleeps for `interval_seconds`, invokes the coroutine, and
repeats.  Graceful shutdown cancels all tasks and awaits completion.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class ScheduledJob:
    """A periodic job definition."""

    name: str
    func: Callable[..., Awaitable[Any]]
    interval_seconds: int
    kwargs: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    _task: asyncio.Task[None] | None = field(default=None, repr=False)


class JobScheduler:
    """Lightweight async scheduler for periodic agent jobs.

    Uses ``asyncio.create_task`` + sleep loops instead of heavy deps like
    APScheduler.

    When *redis_url* is provided, each job execution is guarded by a
    distributed lock so that only one instance across a cluster will run
    the job at a time.

    Usage::

        scheduler = JobScheduler(redis_url="redis://localhost:6379/0")
        scheduler.add_job("nightly_learning", my_coro, interval_seconds=86400)
        await scheduler.start()
        ...
        await scheduler.stop()
    """

    def __init__(self, redis_url: str = "") -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._redis_url = redis_url

    # -- registration --------------------------------------------------------

    def add_job(
        self,
        name: str,
        func: Callable[..., Awaitable[Any]],
        interval_seconds: int,
        enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        """Register a periodic job.

        Args:
            name: Unique identifier for this job.
            func: Async callable to invoke each interval.
            interval_seconds: Seconds between successive invocations.
            enabled: When False the job is registered but not started.
            **kwargs: Additional keyword arguments forwarded to *func*.

        Raises:
            ValueError: If *interval_seconds* is not positive.
        """
        if interval_seconds <= 0:
            raise ValueError(f"interval_seconds must be positive, got {interval_seconds}")
        if name in self._jobs:
            logger.warning("job_replaced", name=name)

        self._jobs[name] = ScheduledJob(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            kwargs=kwargs,
            enabled=enabled,
        )
        logger.info(
            "job_registered",
            name=name,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )

    def remove_job(self, name: str) -> bool:
        """Remove a job by name.  Returns True if the job existed."""
        job = self._jobs.pop(name, None)
        if job is None:
            return False
        if job._task and not job._task.done():
            job._task.cancel()
        logger.info("job_removed", name=name)
        return True

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start all enabled jobs.  Idempotent -- calling twice is a no-op."""
        if self._running:
            logger.debug("scheduler_already_running")
            return
        self._running = True
        for job in self._jobs.values():
            if job.enabled:
                job._task = asyncio.create_task(self._run_loop(job), name=f"scheduler:{job.name}")
        logger.info("scheduler_started", job_count=len(self._jobs))

    async def stop(self) -> None:
        """Stop all running jobs gracefully."""
        self._running = False
        for job in self._jobs.values():
            if job._task and not job._task.done():
                job._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await job._task
                job._task = None
        logger.info("scheduler_stopped")

    # -- internal loop -------------------------------------------------------

    async def _run_loop(self, job: ScheduledJob) -> None:
        """Internal loop for a single job -- sleep, execute, repeat."""
        logger.info(
            "job_loop_started",
            name=job.name,
            interval=job.interval_seconds,
        )
        while self._running:
            try:
                await asyncio.sleep(job.interval_seconds)
                if not self._running:
                    break

                if self._redis_url:
                    await self._run_with_lock(job)
                else:
                    await self._run_job(job)
            except asyncio.CancelledError:
                logger.debug("job_loop_cancelled", name=job.name)
                break
            except Exception:
                job.error_count += 1
                logger.exception(
                    "job_failed",
                    name=job.name,
                    error_count=job.error_count,
                )

    async def _run_job(self, job: ScheduledJob) -> None:
        """Execute a job and update bookkeeping."""
        logger.info("job_executing", name=job.name)
        await job.func(**job.kwargs)
        job.last_run = datetime.now(UTC)
        job.run_count += 1
        logger.info(
            "job_completed",
            name=job.name,
            run_count=job.run_count,
        )

    async def _run_with_lock(self, job: ScheduledJob) -> None:
        """Execute a job under a distributed lock."""
        from shieldops.utils.distributed_lock import DistributedLock

        lock = DistributedLock(
            self._redis_url,
            f"scheduler:{job.name}",
            ttl=max(job.interval_seconds, 300),
        )
        async with lock as acquired:
            if not acquired:
                logger.info(
                    "job_skipped_lock_held",
                    name=job.name,
                )
                return
            await self._run_job(job)

    # -- introspection -------------------------------------------------------

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return status dicts for every registered job."""
        return [
            {
                "name": j.name,
                "interval_seconds": j.interval_seconds,
                "enabled": j.enabled,
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "run_count": j.run_count,
                "error_count": j.error_count,
                "running": j._task is not None and not j._task.done(),
            }
            for j in self._jobs.values()
        ]

    def get_job(self, name: str) -> dict[str, Any] | None:
        """Return status dict for a single job, or None."""
        job = self._jobs.get(name)
        if job is None:
            return None
        return {
            "name": job.name,
            "interval_seconds": job.interval_seconds,
            "enabled": job.enabled,
            "last_run": job.last_run.isoformat() if job.last_run else None,
            "run_count": job.run_count,
            "error_count": job.error_count,
            "running": job._task is not None and not job._task.done(),
        }

    @property
    def running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._running
