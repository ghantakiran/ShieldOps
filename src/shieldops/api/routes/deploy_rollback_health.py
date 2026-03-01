"""Deploy Rollback Health Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_rollback_health import (
    RecoverySpeed,
    RollbackHealthStatus,
    RollbackTrigger,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deploy-rollback-health",
    tags=["Deploy Rollback Health"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deploy rollback health service unavailable")
    return _engine


class RecordRollbackRequest(BaseModel):
    deployment_id: str
    rollback_health_status: RollbackHealthStatus = RollbackHealthStatus.UNTESTED
    rollback_trigger: RollbackTrigger = RollbackTrigger.AUTOMATED
    recovery_speed: RecoverySpeed = RecoverySpeed.MODERATE
    recovery_time_seconds: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    deployment_id: str
    rollback_health_status: RollbackHealthStatus = RollbackHealthStatus.UNTESTED
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/rollbacks")
async def record_rollback(
    body: RecordRollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_rollback(**body.model_dump())
    return result.model_dump()


@router.get("/rollbacks")
async def list_rollbacks(
    status: RollbackHealthStatus | None = None,
    trigger: RollbackTrigger | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rollbacks(
            status=status,
            trigger=trigger,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/rollbacks/{record_id}")
async def get_rollback(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_rollback(record_id)
    if result is None:
        raise HTTPException(404, f"Rollback record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/health")
async def analyze_rollback_health(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_rollback_health()


@router.get("/unhealthy")
async def identify_unhealthy_rollbacks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unhealthy_rollbacks()


@router.get("/recovery-time-rankings")
async def rank_by_recovery_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_recovery_time()


@router.get("/trends")
async def detect_health_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_health_trends()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


drh_route = router
