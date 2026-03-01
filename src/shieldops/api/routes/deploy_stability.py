"""Deployment Stability Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_stability import (
    StabilityMetric,
    StabilityPhase,
    StabilityStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/deploy-stability", tags=["Deploy Stability"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deploy stability service unavailable")
    return _engine


class RecordStabilityRequest(BaseModel):
    deployment_id: str
    stability_phase: StabilityPhase = StabilityPhase.IMMEDIATE
    stability_status: StabilityStatus = StabilityStatus.STABLE
    stability_metric: StabilityMetric = StabilityMetric.ERROR_RATE
    stability_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMeasurementRequest(BaseModel):
    deployment_id: str
    stability_metric: StabilityMetric = StabilityMetric.ERROR_RATE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_stability(
    body: RecordStabilityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_stability(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_stabilities(
    phase: StabilityPhase | None = None,
    status: StabilityStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_stabilities(
            phase=phase,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_stability(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_stability(record_id)
    if result is None:
        raise HTTPException(404, f"Stability record '{record_id}' not found")
    return result.model_dump()


@router.post("/measurements")
async def add_measurement(
    body: AddMeasurementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_measurement(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_stability_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_stability_patterns()


@router.get("/unstable-deployments")
async def identify_unstable_deployments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unstable_deployments()


@router.get("/score-rankings")
async def rank_by_stability_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_stability_score()


@router.get("/trends")
async def detect_stability_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_stability_trends()


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


dst_route = router
