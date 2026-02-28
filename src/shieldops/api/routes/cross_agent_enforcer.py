"""Cross-agent enforcer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.policy.cross_agent_enforcer import (
    EnforcementAction,
    PolicyScope,
    ViolationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cross-agent-enforcer",
    tags=["Cross-Agent Enforcer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cross-agent enforcer service unavailable")
    return _engine


class RecordEnforcementRequest(BaseModel):
    agent_name: str
    policy_scope: PolicyScope = PolicyScope.SINGLE_AGENT
    enforcement_action: EnforcementAction = EnforcementAction.ALLOW
    violation_type: ViolationType = ViolationType.RESOURCE_CONFLICT
    severity_score: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    policy_scope: PolicyScope = PolicyScope.GLOBAL
    enforcement_action: EnforcementAction = EnforcementAction.DENY
    max_violations: int = 0


@router.post("/enforcements")
async def record_enforcement(
    body: RecordEnforcementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_enforcement(**body.model_dump())
    return result.model_dump()


@router.get("/enforcements")
async def list_enforcements(
    agent_name: str | None = None,
    policy_scope: PolicyScope | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_enforcements(
            agent_name=agent_name, policy_scope=policy_scope, limit=limit
        )
    ]


@router.get("/enforcements/{record_id}")
async def get_enforcement(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_enforcement(record_id)
    if result is None:
        raise HTTPException(404, f"Enforcement '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/compliance/{agent_name}")
async def analyze_agent_compliance(
    agent_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_agent_compliance(agent_name)


@router.get("/repeat-violators")
async def identify_repeat_violators(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_repeat_violators()


@router.get("/rankings")
async def rank_by_violation_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_violation_count()


@router.get("/bypass-attempts")
async def detect_policy_bypass_attempts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_policy_bypass_attempts()


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


cap_route = router
