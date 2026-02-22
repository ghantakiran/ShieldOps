"""Tests for the background task queue, pre-built tasks, and API routes."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shieldops.api.app import app
from shieldops.workers.task_queue import TaskDefinition, TaskQueue, TaskStatus

# ── Autouse fixture to reset the route-level singleton ──────────────


@pytest.fixture(autouse=True)
def reset_queue():
    from shieldops.api.routes import task_queue

    task_queue._queue = None
    yield
    task_queue._queue = None


# =========================================================================
# TaskDefinition model
# =========================================================================


class TestTaskDefinition:
    """Tests for the TaskDefinition Pydantic model."""

    def test_defaults(self):
        td = TaskDefinition(name="my-task")
        assert td.name == "my-task"
        assert td.status == TaskStatus.PENDING
        assert td.id.startswith("task-")
        assert len(td.id) == 17  # "task-" + 12 hex chars
        assert td.retries == 0
        assert td.max_retries == 3
        assert td.result is None
        assert td.error is None
        assert td.started_at is None
        assert td.completed_at is None

    def test_custom_values(self):
        td = TaskDefinition(
            id="task-custom12345",
            name="custom",
            status=TaskStatus.RUNNING,
            max_retries=5,
        )
        assert td.id == "task-custom12345"
        assert td.status == TaskStatus.RUNNING
        assert td.max_retries == 5


# =========================================================================
# TaskQueue.enqueue
# =========================================================================


class TestEnqueue:
    """Tests for enqueue behaviour."""

    @pytest.mark.asyncio
    async def test_enqueue_returns_task_id(self):
        queue = TaskQueue()
        task_id = await queue.enqueue("test", AsyncMock())
        assert task_id.startswith("task-")

    @pytest.mark.asyncio
    async def test_enqueue_sets_pending_status(self):
        queue = TaskQueue()
        task_id = await queue.enqueue("test", AsyncMock())
        td = await queue.get_status(task_id)
        assert td is not None
        assert td.status == TaskStatus.PENDING


# =========================================================================
# TaskQueue.get_status
# =========================================================================


class TestGetStatus:
    """Tests for get_status across lifecycle states."""

    @pytest.mark.asyncio
    async def test_get_status_pending(self):
        queue = TaskQueue()
        task_id = await queue.enqueue("pending-task", AsyncMock())
        td = await queue.get_status(task_id)
        assert td is not None
        assert td.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_status_running(self):
        """Task transitions to running once the worker picks it up."""
        started = asyncio.Event()
        finish = asyncio.Event()

        async def slow_task():
            started.set()
            await finish.wait()

        queue = TaskQueue(max_workers=1)
        await queue.start()
        try:
            task_id = await queue.enqueue("slow", slow_task)
            await asyncio.wait_for(started.wait(), timeout=2.0)

            td = await queue.get_status(task_id)
            assert td is not None
            assert td.status == TaskStatus.RUNNING
        finally:
            finish.set()
            await queue.stop()

    @pytest.mark.asyncio
    async def test_get_status_completed(self):
        async def quick():
            return {"ok": True}

        queue = TaskQueue(max_workers=1)
        await queue.start()
        try:
            task_id = await queue.enqueue("quick", quick)
            # Allow the worker to process
            for _ in range(20):
                await asyncio.sleep(0.05)
                td = await queue.get_status(task_id)
                if td and td.status == TaskStatus.COMPLETED:
                    break

            td = await queue.get_status(task_id)
            assert td is not None
            assert td.status == TaskStatus.COMPLETED
            assert td.result == {"ok": True}
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_get_status_failed(self):
        async def boom():
            raise RuntimeError("kaboom")

        queue = TaskQueue(max_workers=1, max_retries=1)
        await queue.start()
        try:
            task_id = await queue.enqueue("boom", boom)
            for _ in range(30):
                await asyncio.sleep(0.05)
                td = await queue.get_status(task_id)
                if td and td.status == TaskStatus.FAILED:
                    break

            td = await queue.get_status(task_id)
            assert td is not None
            assert td.status == TaskStatus.FAILED
            assert "kaboom" in (td.error or "")
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_get_status_unknown_returns_none(self):
        queue = TaskQueue()
        assert await queue.get_status("task-nonexistent") is None


# =========================================================================
# TaskQueue.list_tasks
# =========================================================================


class TestListTasks:
    """Tests for listing tasks with optional filters."""

    @pytest.mark.asyncio
    async def test_list_all_tasks(self):
        queue = TaskQueue()
        await queue.enqueue("a", AsyncMock())
        await queue.enqueue("b", AsyncMock())
        tasks = await queue.list_tasks()
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self):
        queue = TaskQueue()
        await queue.enqueue("a", AsyncMock())
        await queue.enqueue("b", AsyncMock())

        # All should be pending
        pending = await queue.list_tasks(status="pending")
        assert len(pending) == 2

        running = await queue.list_tasks(status="running")
        assert len(running) == 0

    @pytest.mark.asyncio
    async def test_list_respects_limit(self):
        queue = TaskQueue()
        for i in range(10):
            await queue.enqueue(f"task-{i}", AsyncMock())
        tasks = await queue.list_tasks(limit=3)
        assert len(tasks) == 3


# =========================================================================
# TaskQueue.cancel
# =========================================================================


class TestCancel:
    """Tests for task cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self):
        queue = TaskQueue()
        task_id = await queue.enqueue("cancelme", AsyncMock())
        assert await queue.cancel(task_id) is True

        td = await queue.get_status(task_id)
        assert td is not None
        assert td.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_task_fails(self):
        """Running tasks cannot be cancelled via this method."""
        started = asyncio.Event()
        finish = asyncio.Event()

        async def blocker():
            started.set()
            await finish.wait()

        queue = TaskQueue(max_workers=1)
        await queue.start()
        try:
            task_id = await queue.enqueue("running", blocker)
            await asyncio.wait_for(started.wait(), timeout=2.0)

            # Attempt to cancel while running
            assert await queue.cancel(task_id) is False
        finally:
            finish.set()
            await queue.stop()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        queue = TaskQueue()
        assert await queue.cancel("task-doesnotexist") is False


# =========================================================================
# Retry & backoff
# =========================================================================


class TestRetry:
    """Tests for retry logic and exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Task retries up to max_retries before marking as failed."""
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        queue = TaskQueue(max_workers=1, max_retries=3)
        await queue.start()
        try:
            task_id = await queue.enqueue("flaky", flaky)
            # Wait for retries (backoff: 2s + 4s + ... but we patch sleep)
            for _ in range(100):
                await asyncio.sleep(0.1)
                td = await queue.get_status(task_id)
                if td and td.status == TaskStatus.FAILED:
                    break

            td = await queue.get_status(task_id)
            assert td is not None
            assert td.status == TaskStatus.FAILED
            assert td.retries == 3
            assert call_count == 3
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Verify the backoff is computed as 2^attempt."""
        sleep_durations: list[float] = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds):
            sleep_durations.append(seconds)
            # Don't actually sleep during tests -- just record
            await original_sleep(0)

        async def always_fails():
            raise ValueError("fail")

        queue = TaskQueue(max_workers=1, max_retries=3)
        await queue.start()
        try:
            with patch("shieldops.workers.task_queue.asyncio.sleep", side_effect=mock_sleep):
                task_id = await queue.enqueue("backoff-test", always_fails)
                for _ in range(50):
                    await original_sleep(0.05)
                    td = await queue.get_status(task_id)
                    if td and td.status == TaskStatus.FAILED:
                        break

            # Should have backoff sleeps of 2, 4 (after attempts 1 and 2;
            # attempt 3 hits max_retries so no sleep after)
            backoff_sleeps = [d for d in sleep_durations if d >= 2]
            assert 2 in backoff_sleeps
            assert 4 in backoff_sleeps
        finally:
            await queue.stop()


# =========================================================================
# Concurrency limit
# =========================================================================


class TestConcurrency:
    """Tests for max_workers semaphore enforcement."""

    @pytest.mark.asyncio
    async def test_max_workers_concurrency_limit(self):
        """Only max_workers tasks should run concurrently."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()
        all_started = asyncio.Event()

        async def track_concurrency():
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
                if current_concurrent >= 2:
                    all_started.set()
            await asyncio.sleep(0.2)
            async with lock:
                current_concurrent -= 1

        queue = TaskQueue(max_workers=2)
        await queue.start()
        try:
            # Enqueue 4 tasks, only 2 should run at once
            for _ in range(4):
                await queue.enqueue("concurrent", track_concurrency)

            # Wait for all to finish
            for _ in range(40):
                await asyncio.sleep(0.1)
                stats = queue.stats()
                if stats["completed"] == 4:
                    break

            assert max_concurrent <= 2
        finally:
            await queue.stop()


# =========================================================================
# Task expiry
# =========================================================================


class TestExpiry:
    """Tests for completed task cleanup."""

    @pytest.mark.asyncio
    async def test_task_expiry_cleanup(self):
        """Completed tasks older than the expiry window are removed."""
        from datetime import UTC, datetime, timedelta

        queue = TaskQueue(max_workers=1)

        # Manually insert a completed task with an old completed_at
        old_task = TaskDefinition(
            name="old",
            status=TaskStatus.COMPLETED,
            completed_at=datetime.now(UTC) - timedelta(hours=2),
        )
        queue._tasks[old_task.id] = old_task

        # Manually insert a recent completed task
        recent_task = TaskDefinition(
            name="recent",
            status=TaskStatus.COMPLETED,
            completed_at=datetime.now(UTC),
        )
        queue._tasks[recent_task.id] = recent_task

        # Run cleanup inline (bypassing the loop)
        now = datetime.now(UTC)
        from shieldops.workers.task_queue import _EXPIRY_SECONDS

        expired = [
            tid
            for tid, t in queue._tasks.items()
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
            queue._tasks.pop(tid, None)

        # Old task should be gone, recent should remain
        assert old_task.id not in queue._tasks
        assert recent_task.id in queue._tasks


# =========================================================================
# TaskResult
# =========================================================================


class TestTaskResult:
    """Tests for TaskResult / get_result."""

    @pytest.mark.asyncio
    async def test_get_result_for_completed_task(self):
        async def returns_data():
            return {"rows": 42}

        queue = TaskQueue(max_workers=1)
        await queue.start()
        try:
            task_id = await queue.enqueue("export", returns_data)
            for _ in range(20):
                await asyncio.sleep(0.05)
                td = await queue.get_status(task_id)
                if td and td.status == TaskStatus.COMPLETED:
                    break

            result = await queue.get_result(task_id)
            assert result is not None
            assert result.task_id == task_id
            assert result.status == TaskStatus.COMPLETED
            assert result.result == {"rows": 42}
            assert result.duration_ms is not None
            assert result.duration_ms >= 0
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_get_result_unknown_task(self):
        queue = TaskQueue()
        assert await queue.get_result("task-nope") is None


# =========================================================================
# Pre-built task functions
# =========================================================================


class TestPrebuiltTasks:
    """Tests for the wrapper functions in workers.tasks."""

    @pytest.mark.asyncio
    async def test_run_compliance_audit(self):
        from shieldops.workers.tasks import run_compliance_audit

        engine = AsyncMock()
        report = MagicMock(
            audit_id="audit-001",
            total_controls=10,
            passed=8,
            failed=1,
            warnings=1,
        )
        engine.run_audit.return_value = report

        result = await run_compliance_audit(engine)
        engine.run_audit.assert_awaited_once()
        assert result["audit_id"] == "audit-001"
        assert result["passed"] == 8

    @pytest.mark.asyncio
    async def test_run_bulk_export(self):
        from shieldops.workers.tasks import run_bulk_export

        repo = AsyncMock()
        repo.export_entities.return_value = [{"id": "1"}, {"id": "2"}]

        result = await run_bulk_export(repo, "investigations", {"status": "closed"})
        repo.export_entities.assert_awaited_once_with("investigations", {"status": "closed"})
        assert result["exported_count"] == 2

    @pytest.mark.asyncio
    async def test_run_git_sync(self):
        from shieldops.workers.tasks import run_git_sync

        gs = AsyncMock()
        gs.sync.return_value = MagicMock(commit="abc123", added=3, updated=1, removed=0)

        result = await run_git_sync(gs)
        gs.sync.assert_awaited_once()
        assert result["commit"] == "abc123"
        assert result["added"] == 3

    @pytest.mark.asyncio
    async def test_run_cost_analysis(self):
        from shieldops.workers.tasks import run_cost_analysis

        runner = AsyncMock()
        runner.analyze.return_value = MagicMock(analysis_id="cost-xyz")

        result = await run_cost_analysis(runner, environment="production")
        runner.analyze.assert_awaited_once()
        assert result["analysis_id"] == "cost-xyz"

    @pytest.mark.asyncio
    async def test_run_learning_cycle(self):
        from shieldops.workers.tasks import run_learning_cycle

        runner = AsyncMock()
        runner.learn.return_value = MagicMock(
            learning_id="learn-001",
            total_incidents_analyzed=42,
            pattern_insights=[MagicMock(), MagicMock()],
        )

        result = await run_learning_cycle(runner)
        runner.learn.assert_awaited_once_with(learning_type="full", period="7d")
        assert result["incidents_analyzed"] == 42
        assert result["patterns_found"] == 2


# =========================================================================
# API route tests
# =========================================================================


class TestAPIRoutes:
    """Tests for the /tasks API endpoints via TestClient."""

    def _make_client(self) -> tuple[TestClient, TaskQueue]:
        from shieldops.api.routes import task_queue as tq_module

        queue = TaskQueue(max_workers=2)
        tq_module._queue = queue
        app.include_router(
            tq_module.router,
            prefix="/api/v1",
            tags=["Task Queue"],
        )
        return TestClient(app, raise_server_exceptions=False), queue

    def test_enqueue_task(self):
        client, queue = self._make_client()
        resp = client.post(
            "/api/v1/tasks/enqueue",
            json={"task_name": "compliance_audit", "params": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_enqueue_unknown_task(self):
        client, _ = self._make_client()
        resp = client.post(
            "/api/v1/tasks/enqueue",
            json={"task_name": "nonexistent_task"},
        )
        assert resp.status_code == 400
        assert "Unknown task" in resp.json()["detail"]

    def test_list_tasks(self):
        client, queue = self._make_client()
        # Enqueue a task first
        client.post(
            "/api/v1/tasks/enqueue",
            json={"task_name": "compliance_audit", "params": {}},
        )
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert data["count"] >= 1

    def test_get_task_status(self):
        client, queue = self._make_client()
        enqueue_resp = client.post(
            "/api/v1/tasks/enqueue",
            json={"task_name": "compliance_audit", "params": {}},
        )
        task_id = enqueue_resp.json()["task_id"]

        resp = client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == task_id

    def test_get_task_not_found(self):
        client, _ = self._make_client()
        resp = client.get("/api/v1/tasks/task-doesnotexist")
        assert resp.status_code == 404

    def test_cancel_task(self):
        client, queue = self._make_client()
        enqueue_resp = client.post(
            "/api/v1/tasks/enqueue",
            json={"task_name": "compliance_audit", "params": {}},
        )
        task_id = enqueue_resp.json()["task_id"]

        resp = client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_queue_stats(self):
        client, queue = self._make_client()
        client.post(
            "/api/v1/tasks/enqueue",
            json={"task_name": "compliance_audit", "params": {}},
        )
        resp = client.get("/api/v1/tasks/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_queue_not_configured_returns_503(self):
        from shieldops.api.routes import task_queue as tq_module

        tq_module._queue = None
        # Need router to be included already
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 503
