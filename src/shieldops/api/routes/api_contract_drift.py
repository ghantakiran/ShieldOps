"""API Contract Drift Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.api_contract_drift import (
    DriftSeverity,
    DriftSource,
    DriftType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/api-contract-drift",
    tags=["API Contract Drift"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "API contract drift service unavailable")
    return _engine


class RecordDriftRequest(BaseModel):
    contract_id: str
    drift_type: DriftType = DriftType.FIELD_REMOVED
    drift_severity: DriftSeverity = DriftSeverity.NONE
    drift_source: DriftSource = DriftSource.PRODUCER_CHANGE
    drift_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddDetailRequest(BaseModel):
    contract_id: str
    drift_type: DriftType = DriftType.FIELD_REMOVED
    detail_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/drifts")
async def record_drift(
    body: RecordDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_drift(**body.model_dump())
    return result.model_dump()


@router.get("/drifts")
async def list_drifts(
    drift_type: DriftType | None = None,
    severity: DriftSeverity | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_drifts(
            drift_type=drift_type,
            severity=severity,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/drifts/{record_id}")
async def get_drift(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_drift(record_id)
    if result is None:
        raise HTTPException(404, f"Drift record '{record_id}' not found")
    return result.model_dump()


@router.post("/details")
async def add_detail(
    body: AddDetailRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_detail(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_drift_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_drift_patterns()


@router.get("/breaking")
async def identify_breaking_drifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_breaking_drifts()


@router.get("/drift-score-rankings")
async def rank_by_drift_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_drift_score()


@router.get("/trends")
async def detect_drift_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_drift_trends()


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


acd_route = router
