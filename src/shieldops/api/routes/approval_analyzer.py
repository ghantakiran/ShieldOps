"""Change approval analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.approval_analyzer import (
    ApprovalBottleneck,
    ApprovalOutcome,
    ApprovalSpeed,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/approval-analyzer",
    tags=["Approval Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Change approval analyzer service unavailable",
        )
    return _engine


class RecordApprovalRequest(BaseModel):
    change_id: str
    outcome: ApprovalOutcome = ApprovalOutcome.APPROVED
    speed: ApprovalSpeed = ApprovalSpeed.NORMAL
    wait_hours: float = 0.0
    reviewer_id: str = ""
    environment: str = ""
    details: str = ""


class AddBottleneckRequest(BaseModel):
    change_id: str
    bottleneck: ApprovalBottleneck = ApprovalBottleneck.REVIEWER_UNAVAILABLE
    delay_hours: float = 0.0
    resolution: str = ""
    resolved: bool = False


@router.post("/approvals")
async def record_approval(
    body: RecordApprovalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_approval(**body.model_dump())
    return result.model_dump()


@router.get("/approvals")
async def list_approvals(
    change_id: str | None = None,
    outcome: ApprovalOutcome | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_approvals(
            change_id=change_id,
            outcome=outcome,
            limit=limit,
        )
    ]


@router.get("/approvals/{record_id}")
async def get_approval(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_approval(record_id)
    if result is None:
        raise HTTPException(404, f"Approval record '{record_id}' not found")
    return result.model_dump()


@router.post("/bottlenecks")
async def add_bottleneck(
    body: AddBottleneckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_bottleneck(**body.model_dump())
    return result.model_dump()


@router.get("/velocity/{environment}")
async def analyze_approval_velocity(
    environment: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_approval_velocity(environment)


@router.get("/slow-approvals")
async def identify_slow_approvals(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_approvals()


@router.get("/rankings")
async def rank_by_wait_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_wait_time()


@router.get("/bottleneck-analysis")
async def detect_approval_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_approval_bottlenecks()


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


caa_route = router
