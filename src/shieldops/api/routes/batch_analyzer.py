"""Change batch analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.batch_analyzer import BatchRisk, BatchType, ConflictType

logger = structlog.get_logger()
router = APIRouter(
    prefix="/batch-analyzer",
    tags=["Batch Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Batch analyzer service unavailable")
    return _engine


class RecordBatchRequest(BaseModel):
    model_config = {"extra": "forbid"}

    batch_name: str
    batch_type: BatchType = BatchType.SEQUENTIAL
    risk: BatchRisk = BatchRisk.LOW
    change_count: int = 0
    risk_score: float = 0.0
    team: str = ""
    details: str = ""


class AddConflictRequest(BaseModel):
    model_config = {"extra": "forbid"}

    batch_id: str
    conflict_type: ConflictType = ConflictType.RESOURCE
    severity: BatchRisk = BatchRisk.LOW
    description: str = ""


@router.post("/batches")
async def record_batch(
    body: RecordBatchRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_batch(**body.model_dump())
    return result.model_dump()


@router.get("/batches")
async def list_batches(
    batch_type: BatchType | None = None,
    risk: BatchRisk | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_batches(batch_type=batch_type, risk=risk, team=team, limit=limit)
    ]


@router.get("/batches/{record_id}")
async def get_batch(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_batch(record_id)
    if result is None:
        raise HTTPException(404, f"Batch '{record_id}' not found")
    return result.model_dump()


@router.post("/conflicts")
async def add_conflict(
    body: AddConflictRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_conflict(**body.model_dump())
    return result.model_dump()


@router.get("/risk-analysis")
async def analyze_batch_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_batch_risk()


@router.get("/high-risk")
async def identify_high_risk_batches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_batches()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_batch_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_batch_trends()


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


cba_route = router
