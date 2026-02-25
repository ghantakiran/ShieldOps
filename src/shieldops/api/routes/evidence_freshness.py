"""Evidence freshness API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.evidence_freshness import (
    EvidenceCategory,
    FreshnessStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/evidence-freshness",
    tags=["Evidence Freshness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Evidence freshness service unavailable",
        )
    return _engine


class RecordEvidenceRequest(BaseModel):
    evidence_id: str
    category: EvidenceCategory
    control_id: str
    collected_at: float
    expires_at: float
    framework: str = ""
    owner: str = ""


@router.post("/evidence")
async def record_evidence(
    body: RecordEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_evidence(**body.model_dump())
    return record.model_dump()


@router.get("/evidence")
async def list_evidence(
    category: EvidenceCategory | None = None,
    status: FreshnessStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_evidence(
            category=category,
            status=status,
            limit=limit,
        )
    ]


@router.get("/evidence/{record_id}")
async def get_evidence(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_evidence(record_id)
    if record is None:
        raise HTTPException(404, f"Evidence '{record_id}' not found")
    return record.model_dump()


@router.post("/evidence/{record_id}/assess")
async def assess_freshness(
    record_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.assess_freshness(record_id)
    return result.model_dump()


@router.get("/gaps")
async def detect_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    gaps = engine.detect_gaps()
    return [g.model_dump() for g in gaps]


@router.get("/freshness-score")
async def calculate_freshness_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_freshness_score()


@router.get("/expiring-soon")
async def identify_expiring_soon(
    days: int = 30,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_expiring_soon(days=days)


@router.get("/rank")
async def rank_by_urgency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_urgency()


@router.get("/report")
async def generate_freshness_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_freshness_report()
    return report.model_dump()


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


ef_route = router
