"""Policy impact scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.policy_impact import (
    ImpactScope,
    ImpactSeverity,
    PolicyDomain,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/policy-impact",
    tags=["Policy Impact"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Policy impact service unavailable")
    return _engine


class RecordImpactRequest(BaseModel):
    policy_name: str
    domain: PolicyDomain = PolicyDomain.OPERATIONAL
    severity: ImpactSeverity | None = None
    scope: ImpactScope = ImpactScope.SERVICE
    affected_services_count: int = 0
    risk_score: float = 0.0
    details: str = ""


class RecordConflictRequest(BaseModel):
    policy_a: str
    policy_b: str
    conflict_type: str = ""
    severity: ImpactSeverity = ImpactSeverity.MEDIUM
    resolution: str = ""


@router.post("/impacts")
async def record_impact(
    body: RecordImpactRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_impact(**body.model_dump())
    return result.model_dump()


@router.get("/impacts")
async def list_impacts(
    policy_name: str | None = None,
    domain: PolicyDomain | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_impacts(policy_name=policy_name, domain=domain, limit=limit)
    ]


@router.get("/impacts/{record_id}")
async def get_impact(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_impact(record_id)
    if result is None:
        raise HTTPException(404, f"Impact '{record_id}' not found")
    return result.model_dump()


@router.post("/conflicts")
async def record_conflict(
    body: RecordConflictRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_conflict(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{policy_name}")
async def analyze_policy_impact(
    policy_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_policy_impact(policy_name)


@router.get("/high-impact")
async def identify_high_impact_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_policies()


@router.get("/rankings")
async def rank_by_affected_scope(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_affected_scope()


@router.get("/conflicts")
async def detect_policy_conflicts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_policy_conflicts()


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


pis_route = router
