"""Game day planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/game-day-planner", tags=["Game Day Planner"])

_planner: Any = None


def set_planner(planner: Any) -> None:
    global _planner
    _planner = planner


def _get_planner() -> Any:
    if _planner is None:
        raise HTTPException(503, "Game day planner service unavailable")
    return _planner


class CreateGameDayRequest(BaseModel):
    name: str
    scheduled_date: str = ""
    teams: list[str] = []
    objectives: list[str] = []


class AddScenarioRequest(BaseModel):
    name: str
    complexity: str = "BASIC"
    description: str = ""
    target_service: str = ""
    expected_outcome: str = ""


class ScoreScenarioRequest(BaseModel):
    score: float
    actual_outcome: str = ""


@router.post("/game-days")
async def create_game_day(
    body: CreateGameDayRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    gd = planner.create_game_day(**body.model_dump())
    return gd.model_dump()


@router.get("/game-days")
async def list_game_days(
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return [gd.model_dump() for gd in planner.list_game_days(status=status, limit=limit)]


@router.get("/game-days/{gd_id}")
async def get_game_day(
    gd_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    gd = planner.get_game_day(gd_id)
    if gd is None:
        raise HTTPException(404, f"Game day '{gd_id}' not found")
    return gd.model_dump()


@router.post("/game-days/{gd_id}/scenarios")
async def add_scenario(
    gd_id: str,
    body: AddScenarioRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    scenario = planner.add_scenario(game_day_id=gd_id, **body.model_dump())
    if scenario is None:
        raise HTTPException(404, f"Game day '{gd_id}' not found")
    return scenario.model_dump()


@router.post("/scenarios/{scenario_id}/score")
async def score_scenario(
    scenario_id: str,
    body: ScoreScenarioRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    scenario = planner.score_scenario(scenario_id=scenario_id, **body.model_dump())
    if scenario is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    return scenario.model_dump()


@router.get("/team-readiness")
async def calculate_team_readiness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.calculate_team_readiness()


@router.get("/coverage-gaps")
async def identify_coverage_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    planner = _get_planner()
    return planner.identify_coverage_gaps()


@router.get("/action-items")
async def track_action_items(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return planner.track_action_items()


@router.get("/report")
async def generate_game_day_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.generate_game_day_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.get_stats()
