"""Deployment dependency tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deployment_dependency import (
    DependencyDirection,
    DependencyRisk,
    DependencyType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deployment-dependency",
    tags=["Deployment Dependency"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deployment dependency service unavailable")
    return _engine


class RecordDependencyRequest(BaseModel):
    service_name: str
    dep_type: DependencyType = DependencyType.API_CONTRACT
    direction: DependencyDirection = DependencyDirection.UPSTREAM
    risk: DependencyRisk = DependencyRisk.LOW
    depth: int = 0
    details: str = ""


class AddConstraintRequest(BaseModel):
    constraint_name: str
    dep_type: DependencyType = DependencyType.API_CONTRACT
    direction: DependencyDirection = DependencyDirection.UPSTREAM
    priority: int = 0
    description: str = ""


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
    service_name: str | None = None,
    dep_type: DependencyType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dependencies(service_name=service_name, dep_type=dep_type, limit=limit)
    ]


@router.get("/dependencies/{record_id}")
async def get_dependency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_dependency(record_id)
    if result is None:
        raise HTTPException(404, f"Dependency record '{record_id}' not found")
    return result.model_dump()


@router.post("/constraints")
async def add_constraint(
    body: AddConstraintRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_constraint(**body.model_dump())
    return result.model_dump()


@router.get("/service-dependencies/{service_name}")
async def analyze_service_dependencies(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_dependencies(service_name)


@router.get("/breaking")
async def identify_breaking_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_breaking_dependencies()


@router.get("/rankings")
async def rank_by_dependency_depth(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_dependency_depth()


@router.get("/cycles")
async def detect_dependency_cycles(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_dependency_cycles()


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


ddy_route = router
