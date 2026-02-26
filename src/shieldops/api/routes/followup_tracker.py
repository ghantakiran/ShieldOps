"""Post-incident follow-up tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.followup_tracker import (
    FollowupPriority,
    FollowupStatus,
    FollowupType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/followup-tracker",
    tags=["Followup Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Followup tracker service unavailable")
    return _engine


class RecordFollowupRequest(BaseModel):
    service_name: str
    followup_type: FollowupType = FollowupType.ACTION_ITEM
    status: FollowupStatus = FollowupStatus.OPEN
    priority: FollowupPriority = FollowupPriority.MEDIUM
    age_days: float = 0.0
    details: str = ""


class AddAssignmentRequest(BaseModel):
    assignee_name: str
    followup_type: FollowupType = FollowupType.ACTION_ITEM
    status: FollowupStatus = FollowupStatus.OPEN
    due_days: float = 30.0
    description: str = ""


@router.post("/followups")
async def record_followup(
    body: RecordFollowupRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_followup(**body.model_dump())
    return result.model_dump()


@router.get("/followups")
async def list_followups(
    service_name: str | None = None,
    followup_type: FollowupType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_followups(
            service_name=service_name, followup_type=followup_type, limit=limit
        )
    ]


@router.get("/followups/{record_id}")
async def get_followup(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_followup(record_id)
    if result is None:
        raise HTTPException(404, f"Followup '{record_id}' not found")
    return result.model_dump()


@router.post("/assignments")
async def add_assignment(
    body: AddAssignmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assignment(**body.model_dump())
    return result.model_dump()


@router.get("/completion/{service_name}")
async def analyze_followup_completion(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_followup_completion(service_name)


@router.get("/overdue")
async def identify_overdue_items(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_items()


@router.get("/rankings")
async def rank_by_age(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_age()


@router.get("/bottlenecks")
async def detect_followup_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_followup_bottlenecks()


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


fut_route = router
