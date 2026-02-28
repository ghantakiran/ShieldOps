"""Incident replay engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.incident_replay import (
    ReplayFidelity,
    ReplayMode,
    ReplayOutcome,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-replay",
    tags=["Incident Replay"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident replay service unavailable")
    return _engine


class RecordReplayRequest(BaseModel):
    incident_id: str
    mode: ReplayMode = ReplayMode.FULL_REPLAY
    fidelity: ReplayFidelity = ReplayFidelity.EXACT
    outcome: ReplayOutcome = ReplayOutcome.COMPLETED
    effectiveness_score: float = 0.0
    details: str = ""


class AddScenarioRequest(BaseModel):
    scenario_name: str
    mode: ReplayMode = ReplayMode.FULL_REPLAY
    fidelity: ReplayFidelity = ReplayFidelity.HIGH
    target_audience: str = ""
    max_participants: int = 10


@router.post("/replays")
async def record_replay(
    body: RecordReplayRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_replay(**body.model_dump())
    return result.model_dump()


@router.get("/replays")
async def list_replays(
    incident_id: str | None = None,
    mode: ReplayMode | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_replays(incident_id=incident_id, mode=mode, limit=limit)
    ]


@router.get("/replays/{record_id}")
async def get_replay(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_replay(record_id)
    if result is None:
        raise HTTPException(404, f"Replay '{record_id}' not found")
    return result.model_dump()


@router.post("/scenarios")
async def add_scenario(
    body: AddScenarioRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_scenario(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{incident_id}")
async def analyze_replay_effectiveness(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_replay_effectiveness(incident_id)


@router.get("/training-gaps")
async def identify_training_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_training_gaps()


@router.get("/rankings")
async def rank_by_learning_value(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_learning_value()


@router.get("/replay-patterns")
async def detect_replay_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_replay_patterns()


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


ire_route = router
