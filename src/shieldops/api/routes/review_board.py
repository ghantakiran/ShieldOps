"""Incident Review Board API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/review-board", tags=["Review Board"])

_instance: Any = None


def set_board(inst: Any) -> None:
    global _instance
    _instance = inst


def _get_board() -> Any:
    if _instance is None:
        raise HTTPException(503, "Review board service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateReviewRequest(BaseModel):
    incident_id: str = ""
    title: str = ""
    category: str = "process_gap"
    summary: str = ""
    root_cause: str = ""


class AddActionItemRequest(BaseModel):
    review_id: str
    description: str = ""
    priority: str = "backlog"
    assignee: str = ""
    due_date: str = ""


class UpdateActionStatusRequest(BaseModel):
    action_id: str
    status: str = "open"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/reviews")
async def create_review(
    body: CreateReviewRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    result = board.create_review(
        incident_id=body.incident_id,
        title=body.title,
        category=body.category,
        summary=body.summary,
        root_cause=body.root_cause,
    )
    return result.model_dump()


@router.get("/reviews")
async def list_reviews(
    status: str | None = None,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    board = _get_board()
    return [
        r.model_dump()
        for r in board.list_reviews(
            status=status,
            category=category,
            limit=limit,
        )
    ]


@router.get("/reviews/{review_id}")
async def get_review(
    review_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    result = board.get_review(review_id)
    if result is None:
        raise HTTPException(404, f"Review '{review_id}' not found")
    return result.model_dump()


@router.post("/action-items")
async def add_action_item(
    body: AddActionItemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    result = board.add_action_item(
        review_id=body.review_id,
        description=body.description,
        priority=body.priority,
        assignee=body.assignee,
        due_date=body.due_date,
    )
    if result is None:
        raise HTTPException(404, f"Review '{body.review_id}' not found")
    return result.model_dump()


@router.post("/action-items/status")
async def update_action_status(
    body: UpdateActionStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    result = board.update_action_status(
        action_id=body.action_id,
        status=body.status,
    )
    if result is None:
        raise HTTPException(404, f"Action '{body.action_id}' not found")
    return result.model_dump()


@router.get("/completion-rate")
async def completion_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    return board.calculate_completion_rate()


@router.get("/recurring-gaps")
async def recurring_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    board = _get_board()
    return board.identify_recurring_gaps()


@router.get("/reviews/{review_id}/blameless-score")
async def blameless_score(
    review_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    return board.score_blameless_culture(review_id)


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    return board.generate_review_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    return board.get_stats()
