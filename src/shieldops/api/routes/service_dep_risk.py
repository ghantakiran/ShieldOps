"""Service dependency risk scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.service_dep_risk import (
    DependencyDirection,
    DependencyType,
    RiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-dep-risk",
    tags=["Service Dependency Risk"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Service dependency risk service unavailable")
    return _engine


class RecordRiskRequest(BaseModel):
    service: str
    dependency: str
    dep_type: DependencyType = DependencyType.SYNCHRONOUS
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    details: str = ""


class AddRiskFactorRequest(BaseModel):
    service: str
    dependency: str
    factor_name: str
    factor_score: float = 0.0
    weight: float = 1.0


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
    dep_type: DependencyType | None = None,
    risk_level: RiskLevel | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_risks(
            dep_type=dep_type, risk_level=risk_level, service=service, limit=limit
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
        raise HTTPException(404, f"Risk record '{record_id}' not found")
    return result.model_dump()


@router.post("/factors")
async def add_risk_factor(
    body: AddRiskFactorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_risk_factor(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/by-service")
async def analyze_risk_by_service(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_risk_by_service()


@router.get("/high-risk")
async def identify_high_risk_deps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_deps()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_risk_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_risk_trends()


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


sdr_route = router
