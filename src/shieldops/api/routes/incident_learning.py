"""Incident learning API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-learning",
    tags=["Incident Learning"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Incident learning service unavailable")
    return _tracker


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordLessonRequest(BaseModel):
    incident_id: str
    title: str
    description: str = ""
    category: str
    priority: str = "medium"
    service: str = ""
    tags: list[str] = Field(default_factory=list)


class ApplyLessonRequest(BaseModel):
    applied_to_service: str
    applied_by: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/lessons")
async def record_lesson(
    body: RecordLessonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    lesson = tracker.record_lesson(
        incident_id=body.incident_id,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        tags=body.tags,
    )
    return lesson.model_dump()


@router.post("/lessons/{lesson_id}/apply")
async def apply_lesson(
    lesson_id: str,
    body: ApplyLessonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    lesson = tracker.get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(404, f"Lesson '{lesson_id}' not found")
    app = tracker.apply_lesson(
        lesson_id=lesson_id,
        applied_to=body.applied_to_service,
        result=f"Applied by {body.applied_by}",
        success=True,
    )
    return app.model_dump()


@router.get("/lessons")
async def list_lessons(
    category: str | None = None,
    service: str | None = None,
    search: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    if search is not None:
        results = tracker.search_lessons(search)
    else:
        results = tracker.list_lessons(category=category)
    if service is not None:
        results = [les for les in results if service in les.tags or les.incident_id == service]
    return [les.model_dump() for les in results[-limit:]]


@router.get("/lessons/{lesson_id}")
async def get_lesson(
    lesson_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    lesson = tracker.get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(404, f"Lesson '{lesson_id}' not found")
    return lesson.model_dump()


@router.get("/applications")
async def list_applications(
    lesson_id: str | None = None,
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    apps = tracker.get_applications(lesson_id=lesson_id)
    if service is not None:
        apps = [a for a in apps if a.applied_to == service]
    return [a.model_dump() for a in apps[-limit:]]


@router.get("/effective")
async def get_effective_lessons(
    min_applications: int = 2,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    effective = tracker.get_effective_lessons()
    # Filter by minimum application count
    results: list[dict[str, Any]] = []
    for lesson in effective:
        apps = tracker.get_applications(lesson_id=lesson.id)
        if len(apps) >= min_applications:
            data = lesson.model_dump()
            data["application_count"] = len(apps)
            results.append(data)
    return results


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
