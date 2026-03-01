"""Service Dependency Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.service_dependency_scorer import (
    CouplingLevel,
    DependencyDirection,
    DependencyHealth,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-dependency-scorer",
    tags=["Service Dependency Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Service dependency scorer service unavailable")
    return _engine


class RecordDependencyRequest(BaseModel):
    dependency_id: str
    coupling_level: CouplingLevel = CouplingLevel.LOOSE
    dependency_health: DependencyHealth = DependencyHealth.UNKNOWN
    dependency_direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    health_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    dependency_id: str
    coupling_level: CouplingLevel = CouplingLevel.LOOSE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/dependencies")
async def record_dependency(
    body: RecordDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_dependency(**body.model_dump())
    return result.model_dump()


@router.get("/dependencies")
async def list_dependencies(
    coupling_level: CouplingLevel | None = None,
    dependency_health: DependencyHealth | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dependencies(
            coupling_level=coupling_level,
            dependency_health=dependency_health,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/dependencies/{record_id}")
async def get_dependency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_dependency(record_id)
    if result is None:
        raise HTTPException(404, f"Dependency '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_dependency_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_dependency_distribution()


@router.get("/fragile-dependencies")
async def identify_fragile_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_fragile_dependencies()


@router.get("/health-rankings")
async def rank_by_health_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_health_score()


@router.get("/trends")
async def detect_dependency_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_dependency_trends()


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


sdx_route = router
