"""Post-mortem report API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.investigation.postmortem import (
    PostMortemStatus,
    Severity,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/postmortems", tags=["Post-Mortems"])

_generator: Any = None


def set_generator(generator: Any) -> None:
    global _generator
    _generator = generator


def _get_generator() -> Any:
    if _generator is None:
        raise HTTPException(503, "Post-mortem service unavailable")
    return _generator


class GenerateRequest(BaseModel):
    incident_id: str
    title: str
    summary: str = ""
    severity: Severity = Severity.MEDIUM
    contributing_factors: list[dict[str, Any]] = Field(default_factory=list)
    timeline_summary: str = ""
    impact_description: str = ""
    detection_method: str = ""
    resolution_summary: str = ""
    lessons_learned: list[str] = Field(default_factory=list)
    services_affected: list[str] = Field(default_factory=list)
    duration_minutes: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateStatusRequest(BaseModel):
    status: PostMortemStatus


class AddActionItemRequest(BaseModel):
    title: str
    description: str = ""
    assignee: str = ""
    priority: str = "medium"
    due_date: str = ""


@router.post("/generate")
async def generate_postmortem(
    body: GenerateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.generate(**body.model_dump())
    return report.model_dump()


@router.get("")
async def list_postmortems(
    status: PostMortemStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    gen = _get_generator()
    return [r.model_dump() for r in gen.list_reports(status=status, limit=limit)]


@router.get("/action-items/open")
async def get_open_action_items(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    gen = _get_generator()
    return gen.get_open_action_items()


@router.get("/{report_id}")
async def get_postmortem(
    report_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"Post-mortem '{report_id}' not found")
    return report.model_dump()


@router.put("/{report_id}/status")
async def update_postmortem_status(
    report_id: str,
    body: UpdateStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.update_status(report_id, body.status)
    if report is None:
        raise HTTPException(404, f"Post-mortem '{report_id}' not found")
    return report.model_dump()


@router.post("/{report_id}/action-items")
async def add_action_item(
    report_id: str,
    body: AddActionItemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    item = gen.add_action_item(report_id, **body.model_dump())
    if item is None:
        raise HTTPException(404, f"Post-mortem '{report_id}' not found")
    return item.model_dump()
