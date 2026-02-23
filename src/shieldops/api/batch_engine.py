"""Generic batch/bulk API engine with parallel execution.

Provides entity-agnostic batch processing supporting create, update,
delete, and execute operations with dry-run, stop-on-error, and
per-item result tracking.
"""

from __future__ import annotations

import asyncio
import enum
import time
import uuid
from typing import Any, Protocol, runtime_checkable

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class BatchOperation(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"


class BatchJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


# ── Models ───────────────────────────────────────────────────────────


class BatchItem(BaseModel):
    """Single item in a batch request."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    data: dict[str, Any] = Field(default_factory=dict)


class BatchItemResult(BaseModel):
    """Result of processing a single batch item."""

    item_id: str
    success: bool
    error: str = ""
    result: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0


class BatchConfig(BaseModel):
    """Configuration for a batch operation."""

    entity_type: str
    operation: BatchOperation
    items: list[BatchItem] = Field(default_factory=list)
    stop_on_error: bool = False
    dry_run: bool = False
    parallel: bool = True
    max_parallel: int = 10


class BatchResult(BaseModel):
    """Aggregate result of a batch job."""

    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    entity_type: str = ""
    operation: str = ""
    status: BatchJobStatus = BatchJobStatus.PENDING
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[BatchItemResult] = Field(default_factory=list)
    duration_ms: float = 0.0
    dry_run: bool = False
    created_at: float = Field(default_factory=time.time)


# ── Handler protocol ─────────────────────────────────────────────────


@runtime_checkable
class BatchHandler(Protocol):
    """Protocol for entity-specific batch handlers."""

    async def handle_create(self, item: dict[str, Any]) -> dict[str, Any]: ...
    async def handle_update(self, item: dict[str, Any]) -> dict[str, Any]: ...
    async def handle_delete(self, item: dict[str, Any]) -> dict[str, Any]: ...
    async def validate(self, item: dict[str, Any], operation: str) -> str | None: ...


# ── Engine ───────────────────────────────────────────────────────────


class BatchEngine:
    """Generic batch processor with pluggable handlers.

    Parameters
    ----------
    max_batch_size:
        Maximum number of items in a single batch request.
    max_parallel:
        Default parallelism for concurrent item processing.
    job_ttl_hours:
        How long to keep completed job results.
    """

    def __init__(
        self,
        max_batch_size: int = 500,
        max_parallel: int = 10,
        job_ttl_hours: int = 24,
    ) -> None:
        self._handlers: dict[str, BatchHandler] = {}
        self._jobs: dict[str, BatchResult] = {}
        self._max_batch_size = max_batch_size
        self._max_parallel = max_parallel
        self._job_ttl = job_ttl_hours * 3600

    # ── Handler registration ─────────────────────────────────────

    def register_handler(self, entity_type: str, handler: BatchHandler) -> None:
        self._handlers[entity_type] = handler
        logger.info("batch_handler_registered", entity_type=entity_type)

    def get_handler(self, entity_type: str) -> BatchHandler | None:
        return self._handlers.get(entity_type)

    def list_entity_types(self) -> list[str]:
        return list(self._handlers.keys())

    # ── Validation ───────────────────────────────────────────────

    async def validate(self, config: BatchConfig) -> list[dict[str, str]]:
        """Validate all items without executing. Returns list of errors."""
        handler = self._handlers.get(config.entity_type)
        if handler is None:
            return [{"error": f"No handler for entity type: {config.entity_type}"}]

        if len(config.items) > self._max_batch_size:
            return [{"error": f"Batch size {len(config.items)} exceeds max {self._max_batch_size}"}]

        errors: list[dict[str, str]] = []
        for item in config.items:
            err = await handler.validate(item.data, config.operation.value)
            if err:
                errors.append({"item_id": item.id, "error": err})
        return errors

    # ── Execution ────────────────────────────────────────────────

    async def execute(self, config: BatchConfig) -> BatchResult:
        """Execute a batch operation."""
        handler = self._handlers.get(config.entity_type)
        result = BatchResult(
            entity_type=config.entity_type,
            operation=config.operation.value,
            total=len(config.items),
            dry_run=config.dry_run,
        )

        if handler is None:
            result.status = BatchJobStatus.FAILED
            result.failed = len(config.items)
            self._jobs[result.job_id] = result
            return result

        if len(config.items) > self._max_batch_size:
            result.status = BatchJobStatus.FAILED
            self._jobs[result.job_id] = result
            return result

        result.status = BatchJobStatus.RUNNING
        self._jobs[result.job_id] = result
        start = time.time()

        if config.dry_run:
            # Validate only
            for item in config.items:
                err = await handler.validate(item.data, config.operation.value)
                result.results.append(
                    BatchItemResult(
                        item_id=item.id,
                        success=err is None,
                        error=err or "",
                    )
                )
                if err:
                    result.failed += 1
                else:
                    result.succeeded += 1
        elif config.parallel:
            await self._execute_parallel(handler, config, result)
        else:
            await self._execute_sequential(handler, config, result)

        result.duration_ms = round((time.time() - start) * 1000, 2)
        result.status = (
            BatchJobStatus.COMPLETED
            if result.failed == 0
            else BatchJobStatus.PARTIAL
            if result.succeeded > 0
            else BatchJobStatus.FAILED
        )

        self._jobs[result.job_id] = result
        self._cleanup_old_jobs()
        return result

    async def _execute_sequential(
        self, handler: BatchHandler, config: BatchConfig, result: BatchResult
    ) -> None:
        for item in config.items:
            item_result = await self._process_item(handler, item, config.operation)
            result.results.append(item_result)
            if item_result.success:
                result.succeeded += 1
            else:
                result.failed += 1
                if config.stop_on_error:
                    result.skipped = result.total - result.succeeded - result.failed
                    break

    async def _execute_parallel(
        self, handler: BatchHandler, config: BatchConfig, result: BatchResult
    ) -> None:
        sem = asyncio.Semaphore(min(config.max_parallel, self._max_parallel))

        async def _bounded(item: BatchItem) -> BatchItemResult:
            async with sem:
                return await self._process_item(handler, item, config.operation)

        tasks = [_bounded(item) for item in config.items]
        item_results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, ir in enumerate(item_results):
            item_result: BatchItemResult
            if isinstance(ir, Exception):
                item_result = BatchItemResult(
                    item_id=config.items[idx].id,
                    success=False,
                    error=str(ir),
                )
            else:
                assert isinstance(ir, BatchItemResult)
                item_result = ir
            result.results.append(item_result)
            if item_result.success:
                result.succeeded += 1
            else:
                result.failed += 1

    async def _process_item(
        self, handler: BatchHandler, item: BatchItem, operation: BatchOperation
    ) -> BatchItemResult:
        start = time.time()
        try:
            if operation == BatchOperation.CREATE:
                data = await handler.handle_create(item.data)
            elif operation == BatchOperation.UPDATE:
                data = await handler.handle_update(item.data)
            elif operation == BatchOperation.DELETE:
                data = await handler.handle_delete(item.data)
            elif operation == BatchOperation.EXECUTE:
                data = await handler.handle_create(item.data)  # reuse create
            else:
                data = {}
            return BatchItemResult(
                item_id=item.id,
                success=True,
                result=data,
                duration_ms=round((time.time() - start) * 1000, 2),
            )
        except Exception as exc:
            return BatchItemResult(
                item_id=item.id,
                success=False,
                error=str(exc),
                duration_ms=round((time.time() - start) * 1000, 2),
            )

    # ── Job management ───────────────────────────────────────────

    def get_job(self, job_id: str) -> BatchResult | None:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> list[BatchResult]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None

    def _cleanup_old_jobs(self) -> None:
        cutoff = time.time() - self._job_ttl
        to_remove = [jid for jid, job in self._jobs.items() if job.created_at < cutoff]
        for jid in to_remove:
            del self._jobs[jid]

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered_handlers": list(self._handlers.keys()),
            "total_jobs": len(self._jobs),
            "max_batch_size": self._max_batch_size,
        }
