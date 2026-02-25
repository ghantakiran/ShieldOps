"""Incident learning tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.learning_tracker import (
    AdoptionLevel,
    LessonCategory,
    LessonStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-learning",
    tags=["Incident Learning"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident learning service unavailable")
    return _engine


class RecordLessonRequest(BaseModel):
    incident_id: str
    title: str
    category: LessonCategory = LessonCategory.ROOT_CAUSE
    status: LessonStatus = LessonStatus.IDENTIFIED
    team: str = ""
    details: str = ""


class RecordApplicationRequest(BaseModel):
    lesson_id: str
    team: str = ""
    adoption_level: AdoptionLevel = AdoptionLevel.NOT_ADOPTED
    evidence: str = ""


class UpdateStatusRequest(BaseModel):
    status: LessonStatus


@router.post("/lessons")
async def record_lesson(
    body: RecordLessonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_lesson(**body.model_dump())
    return result.model_dump()


@router.get("/lessons")
async def list_lessons(
    incident_id: str | None = None,
    category: LessonCategory | None = None,
    status: LessonStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_lessons(
            incident_id=incident_id, category=category, status=status, limit=limit
        )
    ]


@router.get("/lessons/{record_id}")
async def get_lesson(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_lesson(record_id)
    if result is None:
        raise HTTPException(404, f"Lesson '{record_id}' not found")
    return result.model_dump()


@router.post("/applications")
async def record_application(
    body: RecordApplicationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_application(**body.model_dump())
    return result.model_dump()


@router.put("/lessons/{record_id}/status")
async def update_lesson_status(
    record_id: str,
    body: UpdateStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.update_lesson_status(record_id, body.status)
    if result is None:
        raise HTTPException(404, f"Lesson '{record_id}' not found")
    return result.model_dump()


@router.get("/adoption-rate")
async def calculate_adoption_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_adoption_rate()


@router.get("/unapplied")
async def identify_unapplied_lessons(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unapplied_lessons()


@router.get("/team-learning")
async def analyze_team_learning(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_team_learning()


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


lt_route = router
