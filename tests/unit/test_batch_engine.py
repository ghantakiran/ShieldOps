"""Comprehensive tests for the BatchEngine.

Covers:
- Register handler per entity type
- Execute batch create / update / delete
- Sequential execution
- Parallel execution
- stop_on_error=True stops on first failure
- dry_run=True validates without executing
- Per-item results tracking
- Exceeded max batch size => FAILED
- No handler for entity type => FAILED
- Job management: get / list / delete
- Old job cleanup
- Stats
- Mixed success/failure => PARTIAL status
- Validate without executing
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from shieldops.api.batch_engine import (
    BatchConfig,
    BatchEngine,
    BatchItem,
    BatchJobStatus,
    BatchOperation,
    BatchResult,
)

# =========================================================================
# Mock handler
# =========================================================================


class MockBatchHandler:
    """Test handler that implements the BatchHandler protocol."""

    def __init__(
        self,
        create_result: dict[str, Any] | None = None,
        update_result: dict[str, Any] | None = None,
        delete_result: dict[str, Any] | None = None,
        fail_on: set[str] | None = None,
        validate_error: str | None = None,
    ) -> None:
        self._create_result = create_result or {"created": True}
        self._update_result = update_result or {"updated": True}
        self._delete_result = delete_result or {"deleted": True}
        self._fail_on = fail_on or set()
        self._validate_error = validate_error
        self.create_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    async def handle_create(self, item: dict[str, Any]) -> dict[str, Any]:
        self.create_calls.append(item)
        if item.get("id") in self._fail_on:
            raise RuntimeError(f"create failed for {item}")
        return dict(self._create_result)

    async def handle_update(self, item: dict[str, Any]) -> dict[str, Any]:
        self.update_calls.append(item)
        if item.get("id") in self._fail_on:
            raise RuntimeError(f"update failed for {item}")
        return dict(self._update_result)

    async def handle_delete(self, item: dict[str, Any]) -> dict[str, Any]:
        self.delete_calls.append(item)
        if item.get("id") in self._fail_on:
            raise RuntimeError(f"delete failed for {item}")
        return dict(self._delete_result)

    async def validate(self, item: dict[str, Any], operation: str) -> str | None:
        if self._validate_error:
            return self._validate_error
        return None


def _make_items(count: int, prefix: str = "item") -> list[BatchItem]:
    return [BatchItem(id=f"{prefix}-{i}", data={"name": f"{prefix}-{i}"}) for i in range(count)]


# =========================================================================
# Handler registration
# =========================================================================


class TestHandlerRegistration:
    """Register and retrieve handlers."""

    def test_register_handler(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        assert engine.get_handler("users") is handler

    def test_get_handler_missing(self) -> None:
        engine = BatchEngine()
        assert engine.get_handler("nonexistent") is None

    def test_list_entity_types(self) -> None:
        engine = BatchEngine()
        engine.register_handler("users", MockBatchHandler())
        engine.register_handler("alerts", MockBatchHandler())
        types = engine.list_entity_types()
        assert "users" in types
        assert "alerts" in types

    def test_register_overwrites(self) -> None:
        engine = BatchEngine()
        h1 = MockBatchHandler(create_result={"v": 1})
        h2 = MockBatchHandler(create_result={"v": 2})
        engine.register_handler("users", h1)
        engine.register_handler("users", h2)
        assert engine.get_handler("users") is h2


# =========================================================================
# Batch create / update / delete
# =========================================================================


class TestBatchOperations:
    """Execute batch operations of different types."""

    @pytest.mark.asyncio
    async def test_batch_create(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(3),
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.COMPLETED
        assert result.succeeded == 3
        assert result.failed == 0
        assert len(handler.create_calls) == 3

    @pytest.mark.asyncio
    async def test_batch_update(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.UPDATE,
            items=_make_items(2),
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.succeeded == 2
        assert len(handler.update_calls) == 2

    @pytest.mark.asyncio
    async def test_batch_delete(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.DELETE,
            items=_make_items(2),
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.succeeded == 2
        assert len(handler.delete_calls) == 2


# =========================================================================
# Sequential execution
# =========================================================================


class TestSequentialExecution:
    """parallel=False executes items one by one."""

    @pytest.mark.asyncio
    async def test_sequential_order_preserved(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        items = _make_items(5)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.succeeded == 5
        assert [r.item_id for r in result.results] == [i.id for i in items]


# =========================================================================
# Parallel execution
# =========================================================================


class TestParallelExecution:
    """parallel=True processes items concurrently."""

    @pytest.mark.asyncio
    async def test_parallel_all_succeed(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(10),
            parallel=True,
        )
        result = await engine.execute(config)
        assert result.succeeded == 10
        assert result.status == BatchJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parallel_with_failures(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(fail_on={"fail"})
        engine.register_handler("users", handler)
        items = [
            BatchItem(id="ok-1", data={"id": "ok-1"}),
            BatchItem(id="bad-1", data={"id": "fail"}),
            BatchItem(id="ok-2", data={"id": "ok-2"}),
        ]
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=True,
        )
        result = await engine.execute(config)
        assert result.succeeded == 2
        assert result.failed == 1
        assert result.status == BatchJobStatus.PARTIAL


# =========================================================================
# stop_on_error
# =========================================================================


class TestStopOnError:
    """stop_on_error=True halts processing on first failure."""

    @pytest.mark.asyncio
    async def test_stop_on_error_sequential(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(fail_on={"fail"})
        engine.register_handler("users", handler)
        items = [
            BatchItem(id="ok-1", data={"id": "ok-1"}),
            BatchItem(id="bad-1", data={"id": "fail"}),
            BatchItem(id="ok-2", data={"id": "ok-2"}),
        ]
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=False,
            stop_on_error=True,
        )
        result = await engine.execute(config)
        assert result.succeeded == 1
        assert result.failed == 1
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_no_stop_on_error_processes_all(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(fail_on={"fail"})
        engine.register_handler("users", handler)
        items = [
            BatchItem(id="ok-1", data={"id": "ok-1"}),
            BatchItem(id="bad-1", data={"id": "fail"}),
            BatchItem(id="ok-2", data={"id": "ok-2"}),
        ]
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=False,
            stop_on_error=False,
        )
        result = await engine.execute(config)
        assert result.succeeded == 2
        assert result.failed == 1
        assert result.skipped == 0


# =========================================================================
# dry_run
# =========================================================================


class TestDryRun:
    """dry_run=True validates without calling handlers."""

    @pytest.mark.asyncio
    async def test_dry_run_no_handler_calls(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(3),
            dry_run=True,
        )
        result = await engine.execute(config)
        assert len(handler.create_calls) == 0
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_dry_run_all_valid(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(3),
            dry_run=True,
        )
        result = await engine.execute(config)
        assert result.succeeded == 3
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_dry_run_with_validation_errors(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(validate_error="invalid field")
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(2),
            dry_run=True,
        )
        result = await engine.execute(config)
        assert result.failed == 2
        assert result.succeeded == 0


# =========================================================================
# Per-item results
# =========================================================================


class TestPerItemResults:
    """Each item gets its own BatchItemResult."""

    @pytest.mark.asyncio
    async def test_item_results_count(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(4),
            parallel=False,
        )
        result = await engine.execute(config)
        assert len(result.results) == 4

    @pytest.mark.asyncio
    async def test_item_result_has_duration(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(1),
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.results[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_failed_item_has_error(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(fail_on={"fail"})
        engine.register_handler("users", handler)
        items = [BatchItem(id="bad", data={"id": "fail"})]
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.results[0].success is False
        assert result.results[0].error != ""


# =========================================================================
# Exceeded max batch size
# =========================================================================


class TestMaxBatchSize:
    """Batch exceeding max_batch_size is rejected."""

    @pytest.mark.asyncio
    async def test_exceeded_max_batch_size(self) -> None:
        engine = BatchEngine(max_batch_size=5)
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(10),
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.FAILED

    @pytest.mark.asyncio
    async def test_at_max_batch_size_allowed(self) -> None:
        engine = BatchEngine(max_batch_size=5)
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(5),
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.COMPLETED


# =========================================================================
# No handler for entity type
# =========================================================================


class TestNoHandler:
    """Missing handler for the entity type."""

    @pytest.mark.asyncio
    async def test_no_handler_fails(self) -> None:
        engine = BatchEngine()
        config = BatchConfig(
            entity_type="unknown",
            operation=BatchOperation.CREATE,
            items=_make_items(2),
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.FAILED


# =========================================================================
# Job management
# =========================================================================


class TestJobManagement:
    """get_job, list_jobs, delete_job."""

    @pytest.mark.asyncio
    async def test_get_job(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(1),
        )
        result = await engine.execute(config)
        fetched = engine.get_job(result.job_id)
        assert fetched is not None
        assert fetched.job_id == result.job_id

    @pytest.mark.asyncio
    async def test_get_job_missing(self) -> None:
        engine = BatchEngine()
        assert engine.get_job("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_jobs(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        for i in range(3):
            config = BatchConfig(
                entity_type="users",
                operation=BatchOperation.CREATE,
                items=_make_items(1, prefix=f"job{i}"),
            )
            await engine.execute(config)
        jobs = engine.list_jobs()
        assert len(jobs) == 3

    @pytest.mark.asyncio
    async def test_list_jobs_limit(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        for i in range(5):
            config = BatchConfig(
                entity_type="users",
                operation=BatchOperation.CREATE,
                items=_make_items(1, prefix=f"job{i}"),
            )
            await engine.execute(config)
        jobs = engine.list_jobs(limit=2)
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_delete_job(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(1),
        )
        result = await engine.execute(config)
        assert engine.delete_job(result.job_id) is True
        assert engine.get_job(result.job_id) is None

    def test_delete_job_missing(self) -> None:
        engine = BatchEngine()
        assert engine.delete_job("nonexistent") is False


# =========================================================================
# Old job cleanup
# =========================================================================


class TestJobCleanup:
    """Expired jobs are removed after TTL."""

    @pytest.mark.asyncio
    async def test_old_jobs_cleaned_up(self) -> None:
        engine = BatchEngine(job_ttl_hours=0)  # 0-hour TTL means immediate expiry
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        # Create a job with a very old timestamp
        old_result = BatchResult(
            entity_type="users",
            operation="create",
            status=BatchJobStatus.COMPLETED,
            created_at=time.time() - 100,
        )
        engine._jobs[old_result.job_id] = old_result
        # Execute a new job which triggers cleanup
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(1),
        )
        await engine.execute(config)
        assert engine.get_job(old_result.job_id) is None


# =========================================================================
# Stats
# =========================================================================


class TestStats:
    """get_stats() returns engine summary."""

    @pytest.mark.asyncio
    async def test_stats_registered_handlers(self) -> None:
        engine = BatchEngine()
        engine.register_handler("users", MockBatchHandler())
        engine.register_handler("alerts", MockBatchHandler())
        stats = engine.get_stats()
        assert "users" in stats["registered_handlers"]
        assert "alerts" in stats["registered_handlers"]

    @pytest.mark.asyncio
    async def test_stats_total_jobs(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(1),
        )
        await engine.execute(config)
        stats = engine.get_stats()
        assert stats["total_jobs"] == 1

    def test_stats_max_batch_size(self) -> None:
        engine = BatchEngine(max_batch_size=42)
        stats = engine.get_stats()
        assert stats["max_batch_size"] == 42


# =========================================================================
# Mixed success/failure => PARTIAL status
# =========================================================================


class TestPartialStatus:
    """Some items succeed, some fail => PARTIAL."""

    @pytest.mark.asyncio
    async def test_partial_status(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(fail_on={"fail"})
        engine.register_handler("users", handler)
        items = [
            BatchItem(id="ok-1", data={"id": "ok-1"}),
            BatchItem(id="bad-1", data={"id": "fail"}),
        ]
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.PARTIAL
        assert result.succeeded == 1
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_all_fail_status(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(fail_on={"fail"})
        engine.register_handler("users", handler)
        items = [
            BatchItem(id="bad-1", data={"id": "fail"}),
            BatchItem(id="bad-2", data={"id": "fail"}),
        ]
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=items,
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.FAILED

    @pytest.mark.asyncio
    async def test_all_succeed_status(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(3),
            parallel=False,
        )
        result = await engine.execute(config)
        assert result.status == BatchJobStatus.COMPLETED


# =========================================================================
# Validate without executing
# =========================================================================


class TestValidateOnly:
    """validate() checks items without executing."""

    @pytest.mark.asyncio
    async def test_validate_no_errors(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(3),
        )
        errors = await engine.validate(config)
        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_with_errors(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler(validate_error="bad data")
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(2),
        )
        errors = await engine.validate(config)
        assert len(errors) == 2
        assert all("bad data" in e["error"] for e in errors)

    @pytest.mark.asyncio
    async def test_validate_no_handler(self) -> None:
        engine = BatchEngine()
        config = BatchConfig(
            entity_type="unknown",
            operation=BatchOperation.CREATE,
            items=_make_items(1),
        )
        errors = await engine.validate(config)
        assert len(errors) == 1
        assert "No handler" in errors[0]["error"]

    @pytest.mark.asyncio
    async def test_validate_exceeds_max_size(self) -> None:
        engine = BatchEngine(max_batch_size=2)
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(5),
        )
        errors = await engine.validate(config)
        assert len(errors) == 1
        assert "exceeds max" in errors[0]["error"]


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Miscellaneous edge cases."""

    @pytest.mark.asyncio
    async def test_empty_batch(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=[],
        )
        result = await engine.execute(config)
        assert result.total == 0
        assert result.status == BatchJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_result_has_duration(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.CREATE,
            items=_make_items(2),
        )
        result = await engine.execute(config)
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_result_entity_type_and_operation(self) -> None:
        engine = BatchEngine()
        handler = MockBatchHandler()
        engine.register_handler("users", handler)
        config = BatchConfig(
            entity_type="users",
            operation=BatchOperation.UPDATE,
            items=_make_items(1),
        )
        result = await engine.execute(config)
        assert result.entity_type == "users"
        assert result.operation == "update"
