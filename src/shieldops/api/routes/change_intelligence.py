"""Change intelligence analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-intelligence",
    tags=["Change Intelligence"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Change intelligence service unavailable")
    return _analyzer


class RecordChangeRequest(BaseModel):
    change_type: str = "deployment"
    service: str = ""
    description: str = ""
    author: str = ""
    files_changed: int = 0
    lines_changed: int = 0
    has_db_migration: bool = False
    has_config_change: bool = False
    is_rollback: bool = False


class RecordOutcomeRequest(BaseModel):
    outcome: str


@router.post("/changes")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    change = analyzer.record_change(
        change_type=body.change_type,
        service=body.service,
        description=body.description,
        author=body.author,
        files_changed=body.files_changed,
        lines_changed=body.lines_changed,
        has_db_migration=body.has_db_migration,
        has_config_change=body.has_config_change,
        is_rollback=body.is_rollback,
    )
    return change.model_dump()


@router.get("/changes")
async def list_changes(
    service: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    changes = analyzer.list_changes(service=service, outcome=outcome, limit=limit)
    return [c.model_dump() for c in changes]


@router.get("/changes/{change_id}")
async def get_change(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    change = analyzer.get_change(change_id)
    if change is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return change.model_dump()


@router.get("/risk/{change_id}")
async def predict_risk(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    prediction = analyzer.predict_risk(change_id)
    if prediction is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return prediction.model_dump()


@router.get("/safety-gate/{change_id}")
async def evaluate_safety_gate(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    decision = analyzer.evaluate_safety_gate(change_id)
    if decision is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return decision.model_dump()


@router.post("/changes/{change_id}/outcome")
async def record_outcome(
    change_id: str,
    body: RecordOutcomeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    if not analyzer.record_outcome(change_id, body.outcome):
        raise HTTPException(404, f"Change '{change_id}' not found")
    return {"recorded": True}


@router.get("/risk-factors")
async def get_risk_factors(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_risk_factors(service=service)


@router.get("/success-correlation")
async def get_success_correlation(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_success_correlation(service=service)


@router.get("/high-risk")
async def get_high_risk_changes(
    limit: int = 20,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_high_risk_changes(limit=limit)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
