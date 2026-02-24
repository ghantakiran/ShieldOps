"""Cost simulator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-simulator", tags=["Cost Simulator"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost simulator service unavailable")
    return _engine


class CreateScenarioRequest(BaseModel):
    name: str
    simulation_type: str = "ADD_RESOURCE"
    baseline_monthly_cost: float = 0.0
    resource_name: str = ""
    resource_cost: float = 0.0
    region: str = ""
    provider: str = ""


class CompareRequest(BaseModel):
    scenario_ids: list[str]


@router.post("/scenarios")
async def create_scenario(
    body: CreateScenarioRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    scenario = engine.create_scenario(**body.model_dump())
    return scenario.model_dump()


@router.get("/scenarios")
async def list_scenarios(
    simulation_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_scenarios(simulation_type=simulation_type, status=status, limit=limit)
    ]


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    scenario = engine.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    return scenario.model_dump()


@router.post("/scenarios/{scenario_id}/run")
async def run_simulation(
    scenario_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.run_simulation(scenario_id)
    if result is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    return result.model_dump()


@router.post("/scenarios/compare")
async def compare_scenarios(
    body: CompareRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.compare_scenarios(body.scenario_ids)
    return result.model_dump()


@router.post("/scenarios/{scenario_id}/monthly-impact")
async def estimate_monthly_impact(
    scenario_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.estimate_monthly_impact(scenario_id)
    return result.model_dump()


@router.get("/cost-drivers")
async def identify_cost_drivers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [d.model_dump() for d in engine.identify_cost_drivers()]


@router.get("/budget-breaches")
async def detect_budget_breaches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [b.model_dump() for b in engine.detect_budget_breaches()]


@router.get("/report")
async def generate_simulation_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_simulation_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
