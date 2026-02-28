"""Security posture simulator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.posture_simulator import (
    AttackScenario,
    PostureLevel,
    SimulationResult,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/posture-simulator",
    tags=["Posture Simulator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Posture simulator service unavailable",
        )
    return _engine


class RecordSimulationRequest(BaseModel):
    scenario_name: str
    attack: AttackScenario = AttackScenario.LATERAL_MOVEMENT
    result: SimulationResult = SimulationResult.BLOCKED
    posture: PostureLevel = PostureLevel.ADEQUATE
    risk_score: float = 0.0
    details: str = ""


class AddScenarioRequest(BaseModel):
    scenario_name: str
    attack: AttackScenario = AttackScenario.LATERAL_MOVEMENT
    posture: PostureLevel = PostureLevel.ADEQUATE
    complexity_score: float = 5.0
    auto_remediate: bool = False


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
    scenario_name: str | None = None,
    attack: AttackScenario | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_simulations(
            scenario_name=scenario_name,
            attack=attack,
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
        raise HTTPException(
            404,
            f"Simulation '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/scenarios")
async def add_scenario(
    body: AddScenarioRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_scenario(**body.model_dump())
    return result.model_dump()


@router.get("/strength/{scenario_name}")
async def analyze_strength(
    scenario_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_posture_strength(scenario_name)


@router.get("/bypassed")
async def identify_bypassed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_bypassed_defenses()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/weaknesses")
async def detect_weaknesses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_posture_weaknesses()


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


sps_route = router
