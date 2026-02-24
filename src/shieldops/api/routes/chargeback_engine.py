"""Cost chargeback engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/chargeback-engine",
    tags=["Chargeback Engine"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Chargeback engine service unavailable",
        )
    return _instance


class RecordCostRequest(BaseModel):
    team: str
    department: str = ""
    cost_category: str = "compute"
    total_cost: float = 0.0
    billing_period: str = ""


class CreateRuleRequest(BaseModel):
    cost_category: str = "compute"
    method: str = "proportional_usage"
    team: str = ""
    weight: float = 1.0
    is_active: bool = True


class AllocateCostsRequest(BaseModel):
    billing_period: str


class ComparePeriodsRequest(BaseModel):
    period_a: str
    period_b: str


@router.post("/records")
async def record_cost(
    body: RecordCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_cost(
        **body.model_dump(),
    )
    return record.model_dump()


@router.get("/records")
async def list_records(
    team: str | None = None,
    cost_category: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_records(
            team=team,
            cost_category=cost_category,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_record(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.create_rule(**body.model_dump())
    return rule.model_dump()


@router.post("/allocate")
async def allocate_costs(
    body: AllocateCostsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    records = engine.allocate_costs(
        body.billing_period,
    )
    return [r.model_dump() for r in records]


@router.get("/teams/{team}/share")
async def team_share(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_team_share(team)


@router.get("/anomalies")
async def allocation_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_allocation_anomalies()


@router.post("/compare")
async def compare_periods(
    body: ComparePeriodsRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compare_periods(
        body.period_a,
        body.period_b,
    )


@router.get("/report")
async def chargeback_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_chargeback_report()
    return report.model_dump()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    count = engine.clear_data()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
