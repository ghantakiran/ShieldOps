"""Batch operations API for bulk management.

Provides REST endpoints for bulk-creating investigations, remediations,
and updating statuses across entity types. Operations are processed
asynchronously with job tracking.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()

router = APIRouter()

_repository: Repository | None = None

# In-memory job tracker with auto-expiry (1 hour)
_batch_jobs: dict[str, BatchJobStatus] = {}

_MAX_BATCH_SIZE = 100
_JOB_TTL = timedelta(hours=1)

_VALID_ENTITY_TYPES = {"investigation", "remediation"}
_VALID_OPERATIONS = {"create", "update_status"}


def set_repository(repo: Repository | None) -> None:
    """Set the persistence repository for batch operations."""
    global _repository
    _repository = repo


# --- Models ---


class BatchRequest(BaseModel):
    """Batch operation request."""

    items: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=_MAX_BATCH_SIZE,
        description="List of items to process (1-100).",
    )
    operation: str = Field(
        ...,
        description='Operation type: "create" or "update_status".',
    )
    entity_type: str = Field(
        ...,
        description=('Entity type: "investigation" or "remediation".'),
    )

    @field_validator("operation")
    @classmethod
    def _validate_operation(cls, v: str) -> str:
        if v not in _VALID_OPERATIONS:
            raise ValueError(
                f"Invalid operation '{v}'. Must be one of: {sorted(_VALID_OPERATIONS)}"
            )
        return v

    @field_validator("entity_type")
    @classmethod
    def _validate_entity_type(cls, v: str) -> str:
        if v not in _VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type '{v}'. Must be one of: {sorted(_VALID_ENTITY_TYPES)}"
            )
        return v


class BatchJobStatus(BaseModel):
    """Status of a batch job."""

    job_id: str
    status: str = "pending"
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    completed_at: str | None = None


class BatchResponse(BaseModel):
    """Response returned immediately when a batch is accepted."""

    job_id: str
    status: str
    total: int
    message: str


# --- Background processing ---


def _cleanup_expired_jobs() -> None:
    """Remove batch jobs older than _JOB_TTL."""
    now = datetime.now(UTC)
    expired = [
        jid
        for jid, job in _batch_jobs.items()
        if (job.created_at and (now - datetime.fromisoformat(job.created_at)) > _JOB_TTL)
    ]
    for jid in expired:
        _batch_jobs.pop(jid, None)
    if expired:
        logger.info("batch_jobs_expired", count=len(expired))


async def _create_investigation(item: dict[str, Any], repository: Repository) -> None:
    """Create a single investigation from batch item data."""
    from shieldops.models.base import AlertContext

    alert = AlertContext(
        alert_id=item.get("alert_id", f"alert-{uuid4().hex[:8]}"),
        alert_name=item.get("title", "Batch investigation"),
        severity=item.get("severity", "warning"),
        source="batch_api",
        resource_id=item.get("resource_id"),
        triggered_at=datetime.now(UTC),
        description=item.get("description"),
    )
    from shieldops.agents.investigation.models import (
        InvestigationState,
    )

    state = InvestigationState(
        alert_id=alert.alert_id,
        alert_context=alert,
        current_step="created",
    )
    investigation_id = f"inv-{uuid4().hex[:12]}"
    await repository.save_investigation(investigation_id, state)
    logger.debug(
        "batch_investigation_created",
        investigation_id=investigation_id,
    )


async def _create_remediation(item: dict[str, Any], repository: Repository) -> None:
    """Create a single remediation from batch item data."""
    from shieldops.models.base import (
        Environment,
        RemediationAction,
        RiskLevel,
    )

    env_str = item.get("environment", "production")
    action = RemediationAction(
        id=f"act-{uuid4().hex[:12]}",
        action_type=item.get("action", "restart_service"),
        target_resource=item.get("target", "unknown"),
        environment=Environment(env_str),
        risk_level=RiskLevel(item.get("risk_level", "medium")),
        description=item.get(
            "description",
            f"Batch remediation on {item.get('target', 'unknown')}",
        ),
    )
    from shieldops.agents.remediation.models import (
        RemediationState,
    )

    state = RemediationState(
        action=action,
        current_step="created",
        investigation_id=item.get("investigation_id"),
    )
    remediation_id = f"rem-{uuid4().hex[:12]}"
    await repository.save_remediation(remediation_id, state)
    logger.debug(
        "batch_remediation_created",
        remediation_id=remediation_id,
    )


async def _update_entity_status(
    entity_type: str,
    item: dict[str, Any],
    repository: Repository,
) -> None:
    """Update status on an investigation or remediation."""
    entity_id = item.get("id", "")
    new_status = item.get("status", "")
    if not entity_id or not new_status:
        raise ValueError("Both 'id' and 'status' are required for update_status operations.")

    if entity_type == "investigation":
        existing = await repository.get_investigation(entity_id)
        if existing is None:
            raise ValueError(f"Investigation '{entity_id}' not found.")
        # Lightweight status update via raw session
        # (repository doesn't have a direct status updater,
        # so we re-save with updated status)
        from sqlalchemy import update

        from shieldops.db.models import InvestigationRecord

        async with repository._sf() as session:
            stmt = (
                update(InvestigationRecord)
                .where(InvestigationRecord.id == entity_id)
                .values(status=new_status)
            )
            await session.execute(stmt)
            await session.commit()

    elif entity_type == "remediation":
        existing = await repository.get_remediation(entity_id)
        if existing is None:
            raise ValueError(f"Remediation '{entity_id}' not found.")
        from sqlalchemy import update

        from shieldops.db.models import RemediationRecord

        async with repository._sf() as session:
            stmt = (
                update(RemediationRecord)
                .where(RemediationRecord.id == entity_id)
                .values(status=new_status)
            )
            await session.execute(stmt)
            await session.commit()
    else:
        raise ValueError(f"Unsupported entity_type '{entity_type}'.")


async def _process_batch(
    job_id: str,
    request: BatchRequest,
    repository: Repository,
) -> None:
    """Process batch items in background."""
    job = _batch_jobs.get(job_id)
    if job is None:
        return

    job.status = "processing"
    logger.info(
        "batch_processing_started",
        job_id=job_id,
        total=job.total,
        operation=request.operation,
        entity_type=request.entity_type,
    )

    for i, item in enumerate(request.items):
        try:
            if request.operation == "create":
                if request.entity_type == "investigation":
                    await _create_investigation(item, repository)
                elif request.entity_type == "remediation":
                    await _create_remediation(item, repository)
            elif request.operation == "update_status":
                await _update_entity_status(request.entity_type, item, repository)
            job.succeeded += 1
        except Exception as exc:
            job.failed += 1
            job.errors.append({"index": i, "error": str(exc)})
            logger.warning(
                "batch_item_failed",
                job_id=job_id,
                index=i,
                error=str(exc),
            )

    if job.failed == 0:
        job.status = "completed"
    else:
        job.status = "completed_with_errors"

    job.completed_at = datetime.now(UTC).isoformat()
    logger.info(
        "batch_processing_finished",
        job_id=job_id,
        status=job.status,
        succeeded=job.succeeded,
        failed=job.failed,
    )


# --- Endpoints ---


@router.post("/batch/investigations", status_code=202)
async def batch_create_investigations(
    request: BatchRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> BatchResponse:
    """Bulk create investigations.

    Accepts up to 100 items. Processing happens asynchronously.
    Returns 202 with a job_id to track progress.
    """
    if _repository is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available for batch operations.",
        )

    if request.entity_type != "investigation":
        raise HTTPException(
            status_code=400,
            detail=("entity_type must be 'investigation' for this endpoint."),
        )
    if request.operation != "create":
        raise HTTPException(
            status_code=400,
            detail=("operation must be 'create' for this endpoint."),
        )

    return _enqueue_batch(request, _repository)


@router.post("/batch/remediations", status_code=202)
async def batch_create_remediations(
    request: BatchRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> BatchResponse:
    """Bulk create remediations.

    Accepts up to 100 items. Processing happens asynchronously.
    Returns 202 with a job_id to track progress.
    """
    if _repository is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available for batch operations.",
        )

    if request.entity_type != "remediation":
        raise HTTPException(
            status_code=400,
            detail=("entity_type must be 'remediation' for this endpoint."),
        )
    if request.operation != "create":
        raise HTTPException(
            status_code=400,
            detail=("operation must be 'create' for this endpoint."),
        )

    return _enqueue_batch(request, _repository)


@router.post("/batch/update-status", status_code=202)
async def batch_update_status(
    request: BatchRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> BatchResponse:
    """Bulk update status on any entity type.

    Each item must include 'id' and 'status' fields.
    Processing happens asynchronously.
    """
    if _repository is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available for batch operations.",
        )

    if request.operation != "update_status":
        raise HTTPException(
            status_code=400,
            detail=("operation must be 'update_status' for this endpoint."),
        )

    return _enqueue_batch(request, _repository)


@router.get("/batch/jobs/{job_id}")
async def get_batch_job_status(
    job_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> BatchJobStatus:
    """Check batch job status by job ID."""
    _cleanup_expired_jobs()

    job = _batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found.")
    return job


# --- Internal helpers ---


def _enqueue_batch(request: BatchRequest, repository: Repository) -> BatchResponse:
    """Create a batch job and start background processing."""
    _cleanup_expired_jobs()

    job_id = f"batch-{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    job = BatchJobStatus(
        job_id=job_id,
        status="pending",
        total=len(request.items),
        created_at=now,
    )
    _batch_jobs[job_id] = job

    asyncio.create_task(_process_batch(job_id, request, repository))

    logger.info(
        "batch_job_enqueued",
        job_id=job_id,
        total=len(request.items),
        operation=request.operation,
        entity_type=request.entity_type,
    )

    return BatchResponse(
        job_id=job_id,
        status="pending",
        total=len(request.items),
        message=(f"Batch job accepted. Track progress at GET /batch/jobs/{job_id}"),
    )
