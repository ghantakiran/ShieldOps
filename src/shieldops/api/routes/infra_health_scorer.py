"""Infrastructure health scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.infra_health_scorer import (
    HealthDimension,
    HealthGrade,
    InfraLayer,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/infra-health-scorer",
    tags=["Infra Health Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Infra health scorer service unavailable")
    return _engine


class RecordHealthRequest(BaseModel):
    resource_name: str
    layer: InfraLayer = InfraLayer.COMPUTE
    grade: HealthGrade = HealthGrade.GOOD
    health_score: float = 0.0
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    details: str = ""


class AddDimensionRequest(BaseModel):
    detail_name: str
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    grade: HealthGrade = HealthGrade.GOOD
    score: float = 0.0
    description: str = ""


@router.post("/health")
async def record_health(
    body: RecordHealthRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_health(**body.model_dump())
    return result.model_dump()


@router.get("/health")
async def list_health_records(
    layer: InfraLayer | None = None,
    grade: HealthGrade | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_health_records(layer=layer, grade=grade, limit=limit)
    ]


@router.get("/health/{record_id}")
async def get_health(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_health(record_id)
    if result is None:
        raise HTTPException(404, f"Health record '{record_id}' not found")
    return result.model_dump()


@router.post("/dimensions")
async def add_dimension(
    body: AddDimensionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_dimension(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{layer}")
async def analyze_health_by_layer(
    layer: InfraLayer,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_health_by_layer(layer)


@router.get("/unhealthy")
async def identify_unhealthy_infra(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unhealthy_infra()


@router.get("/rankings")
async def rank_by_health_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_health_score()


@router.get("/trends")
async def detect_health_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


ihs_route = router
