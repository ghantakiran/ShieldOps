"""Change advisory board API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/change-advisory", tags=["Change Advisory"])

_board: Any = None


def set_board(board: Any) -> None:
    global _board
    _board = board


def _get_board() -> Any:
    if _board is None:
        raise HTTPException(503, "Change advisory service unavailable")
    return _board


class SubmitRequestBody(BaseModel):
    title: str
    description: str
    service: str
    category: str
    risk_level: str = "medium"
    requester: str = ""


class CastVoteBody(BaseModel):
    voter: str
    decision: str
    comment: str = ""


@router.post("/requests")
async def submit_request(
    body: SubmitRequestBody,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    request = board.submit_request(
        title=body.title,
        description=body.description,
        service=body.service,
        category=body.category,
        risk_score=(
            0.8 if body.risk_level == "high" else 0.5 if body.risk_level == "medium" else 0.2
        ),
        requester=body.requester,
    )
    return request.model_dump()


@router.post("/requests/{request_id}/vote")
async def cast_vote(
    request_id: str,
    body: CastVoteBody,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    cr = board.get_request(request_id)
    if cr is None:
        raise HTTPException(
            404,
            f"Change request '{request_id}' not found",
        )
    vote = board.cast_vote(
        request_id=request_id,
        reviewer=body.voter,
        decision=body.decision,
        comment=body.comment,
    )
    return vote.model_dump()


@router.post("/requests/{request_id}/finalize")
async def finalize_review(
    request_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    cr = board.get_request(request_id)
    if cr is None:
        raise HTTPException(
            404,
            f"Change request '{request_id}' not found",
        )
    result = board.auto_decide(request_id)
    if result is None:
        return {
            "request_id": request_id,
            "status": "pending",
            "message": "Not all reviewers have voted",
        }
    return result.model_dump()


@router.get("/requests")
async def list_requests(
    status: str | None = None,
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    board = _get_board()
    results = board.list_requests(decision=status)
    if service is not None:
        results = [r for r in results if r.service == service]
    return [r.model_dump() for r in results]


@router.get("/requests/{request_id}")
async def get_request(
    request_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    cr = board.get_request(request_id)
    if cr is None:
        raise HTTPException(
            404,
            f"Change request '{request_id}' not found",
        )
    return cr.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    board = _get_board()
    return board.get_stats()
