"""Capacity Simulation Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_simulation import (
    SimulationConfidence,
    SimulationOutcome,
    SimulationScenario,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-simulation",
    tags=["Capacity Simulation"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity simulation service unavailable")
    return _engine


class RecordSimulationRequest(BaseModel):
    scenario_id: str
    simulation_scenario: SimulationScenario = SimulationScenario.PEAK_LOAD
    simulation_outcome: SimulationOutcome = SimulationOutcome.WITHIN_CAPACITY
    simulation_confidence: SimulationConfidence = SimulationConfidence.UNKNOWN
    capacity_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddResultRequest(BaseModel):
    scenario_id: str
    simulation_scenario: SimulationScenario = SimulationScenario.PEAK_LOAD
    result_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/simulations")
async def record_simulation(
    body: RecordSimulationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_simulation(**body.model_dump())
    return result.model_dump()


@router.get("/simulations")
async def list_simulations(
    scenario: SimulationScenario | None = None,
    outcome: SimulationOutcome | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_simulations(
            scenario=scenario,
            outcome=outcome,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/simulations/{record_id}")
async def get_simulation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_simulation(record_id)
    if result is None:
        raise HTTPException(404, f"Simulation '{record_id}' not found")
    return result.model_dump()


@router.post("/results")
async def add_result(
    body: AddResultRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_result(**body.model_dump())
    return result.model_dump()


@router.get("/outcomes")
async def analyze_simulation_outcomes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_simulation_outcomes()


@router.get("/over-capacity")
async def identify_over_capacity_scenarios(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_capacity_scenarios()


@router.get("/risk-rankings")
async def rank_by_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk()


@router.get("/trends")
async def detect_capacity_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_capacity_trends()


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


cse_route = router
