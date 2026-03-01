"""Commitment Utilization Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.commitment_tracker import (
    CommitmentRisk,
    CommitmentType,
    UtilizationLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/commitment-tracker", tags=["Commitment Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Commitment tracker service unavailable")
    return _engine


class RecordCommitmentRequest(BaseModel):
    commitment_id: str
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    utilization_level: UtilizationLevel = UtilizationLevel.GOOD
    commitment_risk: CommitmentRisk = CommitmentRisk.WELL_BALANCED
    utilization_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddUtilizationRequest(BaseModel):
    detail_name: str
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    utilization_threshold: float = 0.0
    avg_utilization_pct: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_commitment(
    body: RecordCommitmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_commitment(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_commitments(
    ctype: CommitmentType | None = None,
    level: UtilizationLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_commitments(
            ctype=ctype,
            level=level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_commitment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_commitment(record_id)
    if result is None:
        raise HTTPException(404, f"Commitment record '{record_id}' not found")
    return result.model_dump()


@router.post("/utilizations")
async def add_utilization(
    body: AddUtilizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_utilization(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_utilization_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_utilization_patterns()


@router.get("/underutilized")
async def identify_underutilized_commitments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underutilized_commitments()


@router.get("/utilization-rankings")
async def rank_by_utilization_pct(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization_pct()


@router.get("/risks")
async def detect_commitment_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_commitment_risks()


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


cut_route = router
