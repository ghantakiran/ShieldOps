"""Rate limit policy manager routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.rate_limit_policy import (
    PolicyEffectiveness,
    PolicyScope,
    ViolationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/rate-limit-policy",
    tags=["Rate Limit Policy"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Rate limit policy service unavailable")
    return _engine


class RecordPolicyRequest(BaseModel):
    service_name: str
    scope: PolicyScope = PolicyScope.SERVICE
    requests_per_second: int = 0
    burst_limit: int = 0
    effectiveness: PolicyEffectiveness = PolicyEffectiveness.UNTUNED
    details: str = ""


class RecordViolationRequest(BaseModel):
    service_name: str
    violation_type: ViolationType = ViolationType.SOFT_LIMIT
    count: int = 0
    consumer: str = ""
    details: str = ""


@router.post("/policies")
async def record_policy(
    body: RecordPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_policy(**body.model_dump())
    return result.model_dump()


@router.get("/policies")
async def list_policies(
    service_name: str | None = None,
    scope: PolicyScope | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_policies(service_name=service_name, scope=scope, limit=limit)
    ]


@router.get("/policies/{record_id}")
async def get_policy(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_policy(record_id)
    if result is None:
        raise HTTPException(404, f"Policy record '{record_id}' not found")
    return result.model_dump()


@router.post("/violations")
async def record_violation(
    body: RecordViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_violation(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{service_name}")
async def analyze_policy_effectiveness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_policy_effectiveness(service_name)


@router.get("/untuned")
async def identify_untuned_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_untuned_policies()


@router.get("/most-violated")
async def rank_most_violated_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_most_violated_services()


@router.get("/adjustments")
async def recommend_limit_adjustments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.recommend_limit_adjustments()


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


rlp_route = router
