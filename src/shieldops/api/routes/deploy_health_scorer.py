"""Deploy health scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
dhs_route = APIRouter(
    prefix="/deploy-health-scorer",
    tags=["Deploy Health Scorer"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Deploy health scorer service unavailable",
        )
    return _instance


# -- Request models --


class ScoreDeploymentRequest(BaseModel):
    deployment_id: str
    service_name: str = ""
    version: str = ""
    composite_score: float = 100.0
    phase: str = "canary"


class RecordReadingRequest(BaseModel):
    deployment_id: str
    dimension: str = "error_rate_delta"
    value: float = 0.0
    weight: float = 1.0


class CompareRequest(BaseModel):
    deployment_ids: list[str]


# -- Routes --


@dhs_route.post("/scores")
async def score_deployment(
    body: ScoreDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    score = engine.score_deployment(**body.model_dump())
    return score.model_dump()


@dhs_route.get("/scores")
async def list_scores(
    service_name: str | None = None,
    grade: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_scores(
            service_name=service_name,
            grade=grade,
            limit=limit,
        )
    ]


@dhs_route.get("/scores/{score_id}")
async def get_score(
    score_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    score = engine.get_score(score_id)
    if score is None:
        raise HTTPException(404, f"Score '{score_id}' not found")
    return score.model_dump()


@dhs_route.post("/readings")
async def record_reading(
    body: RecordReadingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    reading = engine.record_dimension_reading(**body.model_dump())
    return reading.model_dump()


@dhs_route.get("/readings")
async def list_readings(
    deployment_id: str | None = None,
    dimension: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dimension_readings(
            deployment_id=deployment_id,
            dimension=dimension,
            limit=limit,
        )
    ]


@dhs_route.post("/composite/{deployment_id}")
async def compute_composite(
    deployment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    score = engine.compute_composite_score(deployment_id)
    return score.model_dump()


@dhs_route.post("/compare")
async def compare_deployments(
    body: CompareRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.compare_deployments(body.deployment_ids)


@dhs_route.get("/degradation/{deployment_id}")
async def detect_degradation(
    deployment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_degradation(deployment_id)


@dhs_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_health_report().model_dump()


@dhs_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
