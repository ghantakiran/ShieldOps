"""Platform governance scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.policy.governance_scorer import (
    GovernanceDomain,
    GovernanceGrade,
    GovernanceMaturity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/governance-scorer",
    tags=["Governance Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Governance scorer service unavailable",
        )
    return _engine


class RecordGovernanceRequest(BaseModel):
    domain_name: str
    domain: GovernanceDomain = GovernanceDomain.ACCESS_MANAGEMENT
    grade: GovernanceGrade = GovernanceGrade.ADEQUATE
    maturity: GovernanceMaturity = GovernanceMaturity.DEFINED
    score: float = 0.0
    details: str = ""


class AddMetricRequest(BaseModel):
    domain_name: str
    domain: GovernanceDomain = GovernanceDomain.ACCESS_MANAGEMENT
    grade: GovernanceGrade = GovernanceGrade.ADEQUATE
    min_score: float = 70.0
    review_frequency_days: float = 30.0


@router.post("/records")
async def record_governance(
    body: RecordGovernanceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_governance(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_governance_records(
    domain_name: str | None = None,
    domain: GovernanceDomain | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_governance_records(
            domain_name=domain_name,
            domain=domain,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_governance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_governance(record_id)
    if result is None:
        raise HTTPException(404, f"Governance record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{domain_name}")
async def analyze_governance_by_domain(
    domain_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_governance_by_domain(domain_name)


@router.get("/weak-domains")
async def identify_weak_domains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weak_domains()


@router.get("/rankings")
async def rank_by_governance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_governance_score()


@router.get("/trends")
async def detect_governance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_governance_trends()


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


pgs_route = router
