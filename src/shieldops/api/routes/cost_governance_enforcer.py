"""Cost Governance Enforcer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_governance_enforcer import (
    EnforcementAction,
    PolicyScope,
    ViolationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-governance-enforcer",
    tags=["Cost Governance Enforcer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost governance enforcer service unavailable")
    return _engine


class RecordGovernanceRequest(BaseModel):
    policy_name: str
    violation_type: ViolationType = ViolationType.BUDGET_EXCEEDED
    enforcement_action: EnforcementAction = EnforcementAction.ALERT
    policy_scope: PolicyScope = PolicyScope.ORGANIZATION
    violation_count: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddViolationRequest(BaseModel):
    policy_name: str
    violation_type: ViolationType = ViolationType.BUDGET_EXCEEDED
    violation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/governance")
async def record_governance(
    body: RecordGovernanceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_governance(**body.model_dump())
    return result.model_dump()


@router.get("/governance")
async def list_governance_records(
    violation_type: ViolationType | None = None,
    enforcement_action: EnforcementAction | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_governance_records(
            violation_type=violation_type,
            enforcement_action=enforcement_action,
            team=team,
            limit=limit,
        )
    ]


@router.get("/governance/{record_id}")
async def get_governance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_governance(record_id)
    if result is None:
        raise HTTPException(404, f"Governance record '{record_id}' not found")
    return result.model_dump()


@router.post("/violations")
async def add_violation(
    body: AddViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_violation(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_violation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_violation_distribution()


@router.get("/high-violations")
async def identify_high_violation_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_violation_policies()


@router.get("/violation-rankings")
async def rank_by_violation_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_violation_rate()


@router.get("/trends")
async def detect_governance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
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


cge_route = router
