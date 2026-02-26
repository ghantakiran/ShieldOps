"""Dependency risk scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dependency_risk import (
    MitigationStatus,
    RiskFactor,
    RiskTier,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-risk",
    tags=["Dependency Risk"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dependency risk service unavailable")
    return _engine


class RecordRiskRequest(BaseModel):
    dependency_name: str
    risk_factor: RiskFactor = RiskFactor.VERSION_LAG
    risk_tier: RiskTier | None = None
    risk_score: float = 0.0
    mitigation_status: MitigationStatus = MitigationStatus.UNMITIGATED
    affected_services_count: int = 0
    details: str = ""


class RecordMitigationRequest(BaseModel):
    dependency_name: str
    mitigation_name: str
    status: MitigationStatus = MitigationStatus.IN_PROGRESS
    effectiveness_pct: float = 0.0
    notes: str = ""


@router.post("/risks")
async def record_risk(
    body: RecordRiskRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_risk(**body.model_dump())
    return result.model_dump()


@router.get("/risks")
async def list_risks(
    dependency_name: str | None = None,
    risk_factor: RiskFactor | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_risks(
            dependency_name=dependency_name,
            risk_factor=risk_factor,
            limit=limit,
        )
    ]


@router.get("/risks/{record_id}")
async def get_risk(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_risk(record_id)
    if result is None:
        raise HTTPException(404, f"Risk '{record_id}' not found")
    return result.model_dump()


@router.post("/mitigations")
async def record_mitigation(
    body: RecordMitigationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_mitigation(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{dependency_name}")
async def analyze_dependency_risk(
    dependency_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_dependency_risk(dependency_name)


@router.get("/critical")
async def identify_critical_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_risks()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/unmitigated")
async def detect_unmitigated_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_unmitigated_risks()


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


drs_route = router
