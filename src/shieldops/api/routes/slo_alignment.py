"""SLO alignment validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_alignment import (
    AlignmentDimension,
    AlignmentSeverity,
    AlignmentStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-alignment",
    tags=["SLO Alignment"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO alignment service unavailable")
    return _engine


class RecordAlignmentRequest(BaseModel):
    model_config = {"extra": "forbid"}

    service: str
    dependency: str = ""
    status: AlignmentStatus = AlignmentStatus.UNKNOWN
    dimension: AlignmentDimension = AlignmentDimension.AVAILABILITY
    alignment_score: float = 0.0
    severity: AlignmentSeverity = AlignmentSeverity.INFO
    details: str = ""


class AddGapRequest(BaseModel):
    model_config = {"extra": "forbid"}

    record_id: str
    service: str = ""
    gap_description: str = ""
    severity: AlignmentSeverity = AlignmentSeverity.INFO


@router.post("/alignments")
async def record_alignment(
    body: RecordAlignmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_alignment(**body.model_dump())
    return result.model_dump()


@router.get("/alignments")
async def list_alignments(
    status: AlignmentStatus | None = None,
    dimension: AlignmentDimension | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_alignments(
            status=status, dimension=dimension, service=service, limit=limit
        )
    ]


@router.get("/alignments/{record_id}")
async def get_alignment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_alignment(record_id)
    if result is None:
        raise HTTPException(404, f"Alignment record '{record_id}' not found")
    return result.model_dump()


@router.post("/gaps")
async def add_gap(
    body: AddGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_gap(**body.model_dump())
    return result.model_dump()


@router.get("/by-service")
async def analyze_alignment_by_service(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_alignment_by_service()


@router.get("/misaligned")
async def identify_misaligned_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_misaligned_services()


@router.get("/rankings")
async def rank_by_alignment_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_alignment_score()


@router.get("/trends")
async def detect_alignment_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_alignment_trends()


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


sal_route = router
