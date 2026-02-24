"""Dependency health scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-scorer",
    tags=["Dependency Scorer"],
)

_scorer: Any = None


def set_scorer(scorer: Any) -> None:
    global _scorer
    _scorer = scorer


def _get_scorer() -> Any:
    if _scorer is None:
        raise HTTPException(503, "Dependency scorer service unavailable")
    return _scorer


class RegisterDependencyRequest(BaseModel):
    name: str
    service: str = ""
    dependency_type: str = "external"
    dependents: list[str] | None = None


class RecordHealthCheckRequest(BaseModel):
    dep_id: str
    latency_ms: float = 0.0
    success: bool = True
    error_rate: float = 0.0


@router.post("/dependencies")
async def register_dependency(
    body: RegisterDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    dep = scorer.register_dependency(
        name=body.name,
        service=body.service,
        dependency_type=body.dependency_type,
        dependents=body.dependents,
    )
    return dep.model_dump()


@router.get("/dependencies")
async def list_dependencies(
    grade: str | None = None,
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    deps = scorer.list_dependencies(grade=grade, service=service, limit=limit)
    return [d.model_dump() for d in deps]


@router.get("/dependencies/{dep_id}")
async def get_dependency(
    dep_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    dep = scorer.get_dependency(dep_id)
    if dep is None:
        raise HTTPException(404, f"Dependency '{dep_id}' not found")
    return dep.model_dump()


@router.post("/health-check")
async def record_health_check(
    body: RecordHealthCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.record_health_check(
        dep_id=body.dep_id,
        latency_ms=body.latency_ms,
        success=body.success,
        error_rate=body.error_rate,
    )


@router.get("/health/{dep_id}")
async def compute_health_score(
    dep_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.compute_health_score(dep_id)
    if score is None:
        raise HTTPException(404, f"Dependency '{dep_id}' not found")
    return score


@router.post("/simulate/{dependency_name}")
async def simulate_failure(
    dependency_name: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    sim = scorer.simulate_failure(dependency_name)
    return sim.model_dump()


@router.get("/circuit-breakers")
async def recommend_circuit_breakers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    recs = scorer.recommend_circuit_breakers()
    return [r.model_dump() for r in recs]


@router.get("/degraded")
async def get_degraded_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    deps = scorer.get_degraded_dependencies()
    return [d.model_dump() for d in deps]


@router.get("/risk-ranking")
async def get_risk_ranking(
    limit: int = 20,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return scorer.get_risk_ranking(limit=limit)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()
