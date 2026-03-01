"""Deploy Dependency Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_dependency_tracker import (
    BlockingReason,
    DependencyStatus,
    DependencyType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deploy-dependency-tracker",
    tags=["Deploy Dependency Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deploy dependency tracker service unavailable")
    return _engine


class RecordDependencyRequest(BaseModel):
    deploy_id: str
    dependency_type: DependencyType = DependencyType.SERVICE
    dependency_status: DependencyStatus = DependencyStatus.PENDING
    blocking_reason: BlockingReason = BlockingReason.VERSION_MISMATCH
    wait_time_minutes: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddChainRequest(BaseModel):
    deploy_id: str
    dependency_type: DependencyType = DependencyType.SERVICE
    chain_score: float = 0.0
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
    dependency_type: DependencyType | None = None,
    dependency_status: DependencyStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dependencies(
            dependency_type=dependency_type,
            dependency_status=dependency_status,
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


@router.post("/chains")
async def add_chain(
    body: AddChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_chain(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_dependency_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_dependency_distribution()


@router.get("/blocked-deployments")
async def identify_blocked_deployments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_blocked_deployments()


@router.get("/wait-time-rankings")
async def rank_by_wait_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_wait_time()


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


ddt_route = router
