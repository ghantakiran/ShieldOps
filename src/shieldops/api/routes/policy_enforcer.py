"""Policy enforcement monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.policy_enforcer import (
    EnforcementAction,
    EnforcementScope,
    PolicyCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/policy-enforcer",
    tags=["Policy Enforcer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Policy enforcer service unavailable",
        )
    return _engine


class RecordEnforcementRequest(BaseModel):
    policy_name: str
    action: EnforcementAction = EnforcementAction.AUDIT
    scope: EnforcementScope = EnforcementScope.SERVICE
    category: PolicyCategory = PolicyCategory.SECURITY
    target: str = ""
    details: str = ""


class AddViolationRequest(BaseModel):
    policy_name: str
    scope: EnforcementScope = EnforcementScope.SERVICE
    category: PolicyCategory = PolicyCategory.SECURITY
    target: str = ""
    violation_count: int = 0
    details: str = ""


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
    policy_name: str | None = None,
    action: EnforcementAction | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_enforcements(
            policy_name=policy_name,
            action=action,
            limit=limit,
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
        raise HTTPException(404, f"Enforcement record '{record_id}' not found")
    return result.model_dump()


@router.post("/violations")
async def add_violation(
    body: AddViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_violation(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{policy_name}")
async def analyze_enforcement_by_policy(
    policy_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_enforcement_by_policy(policy_name)


@router.get("/frequent-violations")
async def identify_frequent_violations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequent_violations()


@router.get("/rankings")
async def rank_by_violation_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_violation_count()


@router.get("/trends")
async def detect_enforcement_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_enforcement_trends()


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


pen_route = router
