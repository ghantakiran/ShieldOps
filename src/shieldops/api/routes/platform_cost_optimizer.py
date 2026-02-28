"""Platform cost optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.platform_cost_optimizer import (
    CostDomain,
    OptimizationAction,
    OptimizationStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/platform-cost",
    tags=["Platform Cost"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Platform cost service unavailable",
        )
    return _engine


class RecordOptimizationRequest(BaseModel):
    domain_name: str
    cost_domain: CostDomain = CostDomain.COMPUTE
    action: OptimizationAction = OptimizationAction.RIGHTSIZE
    status: OptimizationStatus = OptimizationStatus.IDENTIFIED
    savings_amount: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    cost_domain: CostDomain = CostDomain.COMPUTE
    action: OptimizationAction = OptimizationAction.RIGHTSIZE
    min_savings_threshold: float = 100.0
    auto_implement: bool = False


@router.post("/optimizations")
async def record_optimization(
    body: RecordOptimizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_optimization(**body.model_dump())
    return result.model_dump()


@router.get("/optimizations")
async def list_optimizations(
    domain_name: str | None = None,
    cost_domain: CostDomain | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_optimizations(
            domain_name=domain_name,
            cost_domain=cost_domain,
            limit=limit,
        )
    ]


@router.get("/optimizations/{record_id}")
async def get_optimization(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_optimization(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Optimization '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency/{domain_name}")
async def analyze_cost_efficiency(
    domain_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_cost_efficiency(domain_name)


@router.get("/rejected")
async def identify_rejected_optimizations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_rejected_optimizations()


@router.get("/rankings")
async def rank_by_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings()


@router.get("/anomalies")
async def detect_cost_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_cost_anomalies()


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


pco_route = router
