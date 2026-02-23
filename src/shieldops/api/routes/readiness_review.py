"""Operational readiness review API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/readiness-reviews", tags=["Readiness Reviews"])

_reviewer: Any = None


def set_reviewer(reviewer: Any) -> None:
    global _reviewer
    _reviewer = reviewer


def _get_reviewer() -> Any:
    if _reviewer is None:
        raise HTTPException(503, "Readiness review service unavailable")
    return _reviewer


class CreateChecklistRequest(BaseModel):
    service: str
    version: str = ""
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddCheckItemRequest(BaseModel):
    name: str
    category: str
    description: str = ""
    required: bool = True


class RunReviewRequest(BaseModel):
    checklist_id: str


class EvaluateItemRequest(BaseModel):
    status: str
    evidence: str = ""
    reviewed_by: str = ""


class WaiveItemRequest(BaseModel):
    reason: str = ""
    waived_by: str = ""


@router.post("/checklists")
async def create_checklist(
    body: CreateChecklistRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    checklist = reviewer.create_checklist(**body.model_dump())
    return checklist.model_dump()


@router.get("/checklists")
async def list_checklists(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reviewer = _get_reviewer()
    return [c.model_dump() for c in reviewer._checklists.values()]


@router.get("/checklists/{checklist_id}")
async def get_checklist(
    checklist_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    checklist = reviewer.get_checklist(checklist_id)
    if checklist is None:
        raise HTTPException(404, f"Checklist '{checklist_id}' not found")
    return checklist.model_dump()


@router.post("/checklists/{checklist_id}/items")
async def add_check_item(
    checklist_id: str,
    body: AddCheckItemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    item = reviewer.add_check_item(checklist_id=checklist_id, **body.model_dump())
    return item.model_dump()


@router.post("/run")
async def run_review(
    body: RunReviewRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    result = reviewer.run_review(body.checklist_id)
    return result.model_dump()


@router.get("/{review_id}")
async def get_review(
    review_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    review = reviewer.get_review(review_id)
    if review is None:
        raise HTTPException(404, f"Review '{review_id}' not found")
    return review.model_dump()


@router.get("")
async def list_reviews(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reviewer = _get_reviewer()
    return [r.model_dump() for r in reviewer.list_reviews(service=service)]


@router.put("/{review_id}/items/{item_id}/waive")
async def waive_item(
    review_id: str,
    item_id: str,
    body: WaiveItemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    # Find checklist_id from review
    review = reviewer.get_review(review_id)
    if review is None:
        raise HTTPException(404, f"Review '{review_id}' not found")
    item = reviewer.waive_item(
        checklist_id=review.checklist_id, item_id=item_id, **body.model_dump()
    )
    if item is None:
        raise HTTPException(404, f"Item '{item_id}' not found")
    return item.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reviewer = _get_reviewer()
    return reviewer.get_stats()
