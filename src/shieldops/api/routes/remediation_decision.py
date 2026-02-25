"""Auto-remediation decision engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.remediation_decision import (
    DecisionOutcome,
    RemediationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/remediation-decision",
    tags=["Remediation Decision"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Remediation decision service unavailable",
        )
    return _engine


class RegisterPolicyRequest(BaseModel):
    name: str
    environment: str = "production"
    max_risk_score: float = 0.8
    allowed_types: list[str] | None = None
    require_approval_above: float = 0.5
    block_above: float = 0.9


class EvaluateDecisionRequest(BaseModel):
    service: str
    remediation_type: RemediationType
    risk_score: float = 0.5
    policy_id: str = ""


class CalculateRiskRequest(BaseModel):
    service: str
    remediation_type: RemediationType
    environment: str = "production"
    blast_radius: int = 1


@router.post("/policies")
async def register_policy(
    body: RegisterPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.register_policy(**body.model_dump())
    return result.model_dump()


@router.get("/policies")
async def list_policies(
    environment: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_policies(environment=environment, limit=limit)]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_policy(policy_id)
    if result is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return result.model_dump()


@router.post("/evaluate")
async def evaluate_decision(
    body: EvaluateDecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.evaluate_decision(**body.model_dump())
    return result.model_dump()


@router.get("/decisions")
async def list_decisions(
    service: str | None = None,
    outcome: DecisionOutcome | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_decisions(service=service, outcome=outcome, limit=limit)
    ]


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_decision(decision_id)
    if result is None:
        raise HTTPException(404, f"Decision '{decision_id}' not found")
    return result.model_dump()


@router.post("/calculate-risk")
async def calculate_risk_score(
    body: CalculateRiskRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_risk_score(**body.model_dump())


@router.get("/trends")
async def get_decision_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_decision_trends()


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


rde_route = router
