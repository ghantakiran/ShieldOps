"""Alert routing optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_routing_optimizer import (
    AlertPriority,
    RoutingOutcome,
    RoutingStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-routing-optimizer",
    tags=["Alert Routing Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Alert routing optimizer unavailable",
        )
    return _engine


class RecordRoutingRequest(BaseModel):
    alert_name: str
    strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    outcome: RoutingOutcome = RoutingOutcome.ACKNOWLEDGED
    priority: AlertPriority = AlertPriority.MEDIUM
    response_time_seconds: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    priority: AlertPriority = AlertPriority.MEDIUM
    max_response_seconds: float = 300.0
    auto_escalate: bool = True


@router.post("/routings")
async def record_routing(
    body: RecordRoutingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_routing(**body.model_dump())
    return result.model_dump()


@router.get("/routings")
async def list_routings(
    alert_name: str | None = None,
    strategy: RoutingStrategy | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_routings(
            alert_name=alert_name,
            strategy=strategy,
            limit=limit,
        )
    ]


@router.get("/routings/{record_id}")
async def get_routing(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_routing(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Routing '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{alert_name}")
async def analyze_routing_effectiveness(
    alert_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_routing_effectiveness(alert_name)


@router.get("/misrouted")
async def identify_misrouted_alerts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_misrouted_alerts()


@router.get("/rankings")
async def rank_by_response_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_response_time()


@router.get("/routing-issues")
async def detect_routing_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_routing_issues()


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


aop_route = router
