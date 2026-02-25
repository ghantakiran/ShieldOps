"""Deployment confidence scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deployment_confidence import (
    ConfidenceFactor,
    ConfidenceLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deployment-confidence",
    tags=["Deployment Confidence"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deployment confidence service unavailable")
    return _engine


class RecordFactorRequest(BaseModel):
    deployment_id: str
    factor: ConfidenceFactor = ConfidenceFactor.TEST_COVERAGE
    score: float = 0.0
    weight: float = 1.0
    details: str = ""


class AssessDeploymentRequest(BaseModel):
    deployment_id: str
    service: str = ""


@router.post("/factors")
async def record_factor(
    body: RecordFactorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_factor(**body.model_dump())
    return result.model_dump()


@router.get("/assessments")
async def list_assessments(
    service: str | None = None,
    level: ConfidenceLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_assessments(service=service, level=level, limit=limit)
    ]


@router.get("/assessments/{record_id}")
async def get_assessment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_assessment(record_id)
    if result is None:
        raise HTTPException(404, f"Assessment '{record_id}' not found")
    return result.model_dump()


@router.post("/assess")
async def assess_deployment(
    body: AssessDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.assess_deployment(**body.model_dump())
    return result.model_dump()


@router.get("/low-confidence")
async def identify_low_confidence_deployments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_confidence_deployments()


@router.get("/factor-trends")
async def analyze_factor_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_factor_trends()


@router.get("/compare/{dep_id_a}/{dep_id_b}")
async def compare_deployments(
    dep_id_a: str,
    dep_id_b: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compare_deployments(dep_id_a, dep_id_b)


@router.get("/trend/{service}")
async def calculate_service_confidence_trend(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.calculate_service_confidence_trend(service)


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


dc_route = router
