"""DORA metrics API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/dora", tags=["DORA Metrics"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "DORA metrics service unavailable")
    return _engine


class DeploymentRequest(BaseModel):
    service: str
    environment: str = "production"
    commit_sha: str = ""
    lead_time_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureRequest(BaseModel):
    service: str
    deployment_id: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoveryRequest(BaseModel):
    service: str
    failure_id: str = ""
    recovery_time_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/deployments")
async def record_deployment(
    body: DeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_deployment(**body.model_dump())
    return record.model_dump()


@router.post("/failures")
async def record_failure(
    body: FailureRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_failure(**body.model_dump())
    return record.model_dump()


@router.post("/recoveries")
async def record_recovery(
    body: RecoveryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_recovery(**body.model_dump())
    return record.model_dump()


@router.get("/metrics/{service}")
async def get_metrics(
    service: str,
    period_days: int | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    snapshot = engine.compute_snapshot(service, period_days=period_days)
    return snapshot.model_dump()


@router.get("/trends/{service}")
async def get_trends(
    service: str,
    periods: int = 4,
    period_days: int | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [s.model_dump() for s in engine.get_trends(service, periods, period_days)]


@router.get("/summary")
async def get_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
