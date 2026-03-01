"""Customer Impact Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.customer_impact import (
    CustomerTier,
    ImpactCategory,
    ImpactSeverity,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/customer-impact", tags=["Customer Impact"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Customer impact service unavailable")
    return _engine


class RecordImpactRequest(BaseModel):
    incident_id: str
    impact_category: ImpactCategory = ImpactCategory.AVAILABILITY
    customer_tier: CustomerTier = CustomerTier.FREE
    impact_severity: ImpactSeverity = ImpactSeverity.MINOR
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddDetailRequest(BaseModel):
    incident_id: str
    impact_category: ImpactCategory = ImpactCategory.AVAILABILITY
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_impact(
    body: RecordImpactRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_impact(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_impacts(
    category: ImpactCategory | None = None,
    tier: CustomerTier | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_impacts(
            category=category,
            tier=tier,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_impact(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_impact(record_id)
    if result is None:
        raise HTTPException(404, f"Impact record '{record_id}' not found")
    return result.model_dump()


@router.post("/details")
async def add_detail(
    body: AddDetailRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_detail(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_customer_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_customer_impact()


@router.get("/high-impact-incidents")
async def identify_high_impact_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_incidents()


@router.get("/score-rankings")
async def rank_by_impact_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_score()


@router.get("/patterns")
async def detect_impact_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_impact_patterns()


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


cis_route = router
