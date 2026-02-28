"""Chaos experiment automator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.chaos_automator import (
    BlastRadius,
    ChaosOutcome,
    ChaosType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/chaos-automator",
    tags=["Chaos Automator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Chaos-automator service unavailable",
        )
    return _engine


class RecordExperimentRequest(BaseModel):
    experiment_name: str
    chaos_type: ChaosType = ChaosType.LATENCY_INJECTION
    outcome: ChaosOutcome = ChaosOutcome.PASSED
    blast_radius: BlastRadius = BlastRadius.SINGLE_POD
    impact_score: float = 0.0
    details: str = ""


class AddScheduleRequest(BaseModel):
    schedule_name: str
    chaos_type: ChaosType = ChaosType.LATENCY_INJECTION
    blast_radius: BlastRadius = BlastRadius.SINGLE_POD
    frequency_days: int = 7
    auto_rollback: bool = True


@router.post("/experiments")
async def record_experiment(
    body: RecordExperimentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_experiment(**body.model_dump())
    return result.model_dump()


@router.get("/experiments")
async def list_experiments(
    experiment_name: str | None = None,
    chaos_type: ChaosType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_experiments(
            experiment_name=experiment_name,
            chaos_type=chaos_type,
            limit=limit,
        )
    ]


@router.get("/experiments/{record_id}")
async def get_experiment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_experiment(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Experiment '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/schedules")
async def add_schedule(
    body: AddScheduleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_schedule(**body.model_dump())
    return result.model_dump()


@router.get("/results/{experiment_name}")
async def analyze_experiment_results(
    experiment_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_experiment_results(experiment_name)


@router.get("/failed-experiments")
async def identify_failed_experiments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_experiments()


@router.get("/rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


@router.get("/regressions")
async def detect_experiment_regressions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_experiment_regressions()


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


cxa_route = router
