"""Change risk scoring API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/change-risk", tags=["Change Risk"])

_scorer: Any = None


def set_scorer(scorer: Any) -> None:
    global _scorer
    _scorer = scorer


def _get_scorer() -> Any:
    if _scorer is None:
        raise HTTPException(503, "Change risk scoring service unavailable")
    return _scorer


class RecordChangeRequest(BaseModel):
    service: str
    change_type: str
    description: str = ""
    author: str = ""
    environment: str = "production"
    files_changed: int = 0
    lines_changed: int = 0
    rollback_available: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarkOutcomeRequest(BaseModel):
    success: bool


@router.post("/changes")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    record = scorer.record_change(**body.model_dump())
    return record.model_dump()


@router.get("/changes")
async def list_changes(
    service: str | None = None,
    change_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [r.model_dump() for r in scorer.list_changes(service=service, change_type=change_type)]


@router.post("/score/{change_id}")
async def score_change(
    change_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.score_change(change_id)
    return score.model_dump()


@router.get("/scores/{change_id}")
async def get_score(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.get_score(change_id)
    if score is None:
        raise HTTPException(404, f"Score for '{change_id}' not found")
    return score.model_dump()


@router.get("/high-risk")
async def get_high_risk_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.get_high_risk_changes()]


@router.get("/history/{service}")
async def get_service_risk_history(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.get_service_risk_history(service)]


@router.put("/outcome/{change_id}")
async def mark_outcome(
    change_id: str,
    body: MarkOutcomeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    scorer = _get_scorer()
    scorer.mark_outcome(change_id, body.success)
    return {"status": "recorded"}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()
