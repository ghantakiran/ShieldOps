"""Team workload balancer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.workload_balancer import (
    BalanceStatus,
    RebalanceAction,
    WorkloadType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/workload-balancer",
    tags=["Workload Balancer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Workload balancer service unavailable")
    return _engine


class RecordWorkloadRequest(BaseModel):
    team_name: str
    workload_type: WorkloadType = WorkloadType.INCIDENTS
    status: BalanceStatus = BalanceStatus.BALANCED
    workload_score: float = 0.0
    details: str = ""


class AddAssignmentRequest(BaseModel):
    assignment_name: str
    workload_type: WorkloadType = WorkloadType.INCIDENTS
    action: RebalanceAction = RebalanceAction.NO_ACTION
    impact_score: float = 0.0
    description: str = ""


@router.post("/workloads")
async def record_workload(
    body: RecordWorkloadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_workload(**body.model_dump())
    return result.model_dump()


@router.get("/workloads")
async def list_workloads(
    team_name: str | None = None,
    workload_type: WorkloadType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_workloads(
            team_name=team_name, workload_type=workload_type, limit=limit
        )
    ]


@router.get("/workloads/{record_id}")
async def get_workload(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_workload(record_id)
    if result is None:
        raise HTTPException(404, f"Workload record '{record_id}' not found")
    return result.model_dump()


@router.post("/assignments")
async def add_assignment(
    body: AddAssignmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assignment(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{team_name}")
async def analyze_workload_by_team(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_workload_by_team(team_name)


@router.get("/overloaded")
async def identify_overloaded_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overloaded_teams()


@router.get("/rankings")
async def rank_by_workload_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_workload_score()


@router.get("/imbalances")
async def detect_workload_imbalance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_workload_imbalance()


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


twb_route = router
