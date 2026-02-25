"""Latency budget tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
lbt_route = APIRouter(
    prefix="/latency-budget-tracker",
    tags=["Latency Budget Tracker"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Latency budget tracker service unavailable",
        )
    return _instance


# -- Request models --


class CreateBudgetRequest(BaseModel):
    endpoint: str
    budget_ms: float = 200.0
    tier: str = "standard"
    percentile: str = "p95"


class RecordMeasurementRequest(BaseModel):
    budget_id: str
    measured_ms: float


class AdjustBudgetRequest(BaseModel):
    budget_id: str
    new_budget_ms: float


# -- Routes --


@lbt_route.post("/budgets")
async def create_budget(
    body: CreateBudgetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    budget = engine.create_budget(**body.model_dump())
    return budget.model_dump()


@lbt_route.get("/budgets")
async def list_budgets(
    endpoint: str | None = None,
    tier: str | None = None,
    compliance: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        b.model_dump()
        for b in engine.list_budgets(
            endpoint=endpoint,
            tier=tier,
            compliance=compliance,
            limit=limit,
        )
    ]


@lbt_route.get("/budgets/{budget_id}")
async def get_budget(
    budget_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    budget = engine.get_budget(budget_id)
    if budget is None:
        raise HTTPException(404, f"Budget '{budget_id}' not found")
    return budget.model_dump()


@lbt_route.post("/measurements")
async def record_measurement(
    body: RecordMeasurementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.record_measurement(
        body.budget_id,
        body.measured_ms,
    )


@lbt_route.get("/violations")
async def list_violations(
    budget_id: str | None = None,
    endpoint: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        v.model_dump()
        for v in engine.list_violations(
            budget_id=budget_id,
            endpoint=endpoint,
            limit=limit,
        )
    ]


@lbt_route.get("/compliance/{budget_id}")
async def check_compliance(
    budget_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.check_compliance(budget_id)


@lbt_route.get("/chronic-violators")
async def get_chronic_violators(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [b.model_dump() for b in engine.find_chronic_violators()]


@lbt_route.post("/adjust")
async def adjust_budget(
    body: AdjustBudgetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.adjust_budget(body.budget_id, body.new_budget_ms)
    if not result:
        raise HTTPException(404, f"Budget '{body.budget_id}' not found")
    return {"adjusted": True, "budget_id": body.budget_id}


@lbt_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_budget_report().model_dump()


@lbt_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
