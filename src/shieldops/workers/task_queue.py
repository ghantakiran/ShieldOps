"""In-memory background task queue with concurrency control and retry logic.

Provides an asyncio-based task queue for heavy one-off operations such as
compliance audits, bulk exports, and git syncs.  Uses an ``asyncio.Semaphore``
to cap concurrency and exponential backoff for automatic retries.

Usage::

    queue = TaskQueue(max_workers=4, max_retries=3)
    await queue.start()
    task_id = await queue.enqueue("audit", run_compliance_audit, engine=engine)
    status = await queue.get_status(task_id)
    await queue.stop()
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Completed tasks are purged after this many seconds.
_EXPIRY_SECONDS: int = 3600  # 1 hour


# ── Enums & Models ────────────────────────────────────────────────


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskDefinition(BaseModel):
    """Full task metadata stored in the queue."""

    id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:12]}")
    name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any | None = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 3


class TaskResult(BaseModel):
    """Lightweight result view returned to callers."""

    task_id: str
    status: TaskStatus
    result: Any | None = None
    error: str | None = None
    duration_ms: float | None = None


# ── Task Queue ────────────────────────────────────────────────────


class TaskQueue:
    """Async background task queue with bounded concurrency and retries.

    Args:
        max_workers: Maximum number of tasks executing concurrently.
        max_retries: Default retry limit for each task.
    """

    def __init__(self, max_workers: int = 4, max_retries: int = 3) -> None:
        self._max_workers = max_workers
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_workers)
        self._tasks: dict[str, TaskDefinition] = {}
        self._callables: dict[str, tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = {}
        self._pending: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task[None] | None = None
        self._active_tasks: dict[str, asyncio.Task[Any]] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    # ── Public API ─────────────────────────────────────────────────

    async def enqueue(
        self,
        name: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Submit a task for background execution.

        Returns the task ID that can be used to poll status/results.
        """
        task_def = TaskDefinition(
            name=name,
            max_retries=self._max_retries,
        )
        self._tasks[task_def.id] = task_def
        self._callables[task_def.id] = (func, args, kwargs)
        await self._pending.put(task_def.id)

        logger.info(
            "task_enqueued",
            task_id=task_def.id,
            name=name,
        )
        return task_def.id

    async def get_status(self, task_id: str) -> TaskDefinition | None:
        """Return the full task definition, or ``None`` if not found."""
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TaskDefinition]:
        """List tasks, optionally filtered by status.

        Results are ordered newest-first and capped at *limit*.
        """
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.

        Running tasks cannot be cancelled -- returns ``False`` in that case.
        """
        task_def = self._tasks.get(task_id)
        if task_def is None:
            return False
        if task_def.status != TaskStatus.PENDING:
            return False

        task_def.status = TaskStatus.CANCELLED
        task_def.completed_at = datetime.now(UTC)
        logger.info("task_cancelled", task_id=task_id)
        return True

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Build a lightweight result for a task, or ``None`` if unknown."""
        task_def = self._tasks.get(task_id)
        if task_def is None:
            return None

        duration_ms: float | None = None
        if task_def.started_at and task_def.completed_at:
            delta = task_def.completed_at - task_def.started_at
            duration_ms = delta.total_seconds() * 1000

        return TaskResult(
            task_id=task_def.id,
            status=task_def.status,
            result=task_def.result,
            error=task_def.error,
            duration_ms=duration_ms,
        )

    def stats(self) -> dict[str, int]:
        """Return counts of tasks grouped by status."""
        counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
        for t in self._tasks.values():
            counts[t.status.value] += 1
        counts["total"] = len(self._tasks)
        return counts

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the worker loop.  Idempotent."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(), name="task_queue:worker")
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="task_queue:cleanup")
        logger.info("task_queue_started", max_workers=self._max_workers)

    async def stop(self) -> None:
        """Gracefully stop the queue, waiting for in-flight tasks."""
        self._running = False

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

        # Wait for active execution tasks to finish
        for task in list(self._active_tasks.values()):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._active_tasks.clear()

        logger.info("task_queue_stopped")

    # ── Internal ───────────────────────────────────────────────────

    async def _worker_loop(self) -> None:
        """Consume from the pending queue and dispatch workers."""
        while self._running:
            try:
                task_id = await asyncio.wait_for(self._pending.get(), timeout=1.0)
            except TimeoutError:
                continue

            task_def = self._tasks.get(task_id)
            if task_def is None or task_def.status == TaskStatus.CANCELLED:
                continue

            # Spawn an execution coroutine bounded by the semaphore
            t = asyncio.create_task(self._execute(task_id), name=f"task_queue:exec:{task_id}")
            self._active_tasks[task_id] = t

            def _on_done(_t: asyncio.Task[Any], tid: str = task_id) -> None:
                self._active_tasks.pop(tid, None)

            t.add_done_callback(_on_done)

    async def _execute(self, task_id: str) -> None:
        """Run a single task with retry logic under the semaphore."""
        task_def = self._tasks[task_id]
        func, args, kwargs = self._callables[task_id]

        async with self._semaphore:
            task_def.status = TaskStatus.RUNNING
            task_def.started_at = datetime.now(UTC)

            while True:
                try:
                    result = await func(*args, **kwargs)
                    task_def.status = TaskStatus.COMPLETED
                    task_def.result = result
                    task_def.completed_at = datetime.now(UTC)
                    logger.info(
                        "task_completed",
                        task_id=task_id,
                        name=task_def.name,
                    )
                    break
                except Exception as exc:
                    task_def.retries += 1
                    logger.warning(
                        "task_attempt_failed",
                        task_id=task_id,
                        name=task_def.name,
                        attempt=task_def.retries,
                        error=str(exc),
                    )
                    if task_def.retries >= task_def.max_retries:
                        task_def.status = TaskStatus.FAILED
                        task_def.error = str(exc)
                        task_def.completed_at = datetime.now(UTC)
                        logger.error(
                            "task_failed",
                            task_id=task_id,
                            name=task_def.name,
                            retries=task_def.retries,
                        )
                        break

                    # Exponential backoff: 2^attempt seconds
                    backoff = 2**task_def.retries
                    await asyncio.sleep(backoff)

        # Clean up the callable reference
        self._callables.pop(task_id, None)

    async def _cleanup_loop(self) -> None:
        """Periodically remove expired completed/failed/cancelled tasks."""
        while self._running:
            try:
                await asyncio.sleep(60)  # check every minute
            except asyncio.CancelledError:
                break

            now = datetime.now(UTC)
            expired = [
                tid
                for tid, t in self._tasks.items()
                if t.status
                in (
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                )
                and t.completed_at is not None
                and (now - t.completed_at).total_seconds() >= _EXPIRY_SECONDS
            ]
            for tid in expired:
                self._tasks.pop(tid, None)
                self._callables.pop(tid, None)
                logger.debug("task_expired", task_id=tid)
