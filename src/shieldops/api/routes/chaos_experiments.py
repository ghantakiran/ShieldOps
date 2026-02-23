"""Chaos experiment tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/chaos-experiments", tags=["Chaos Experiments"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Chaos experiment service unavailable")
    return _tracker


class CreateExperimentRequest(BaseModel):
    name: str
    experiment_type: str
    target_service: str
    hypothesis: str = ""
    blast_radius: str = "single-service"
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompleteExperimentRequest(BaseModel):
    steady_state_met: bool
    findings: list[str] = Field(default_factory=list)


class AbortExperimentRequest(BaseModel):
    reason: str = ""


class RecordResultRequest(BaseModel):
    experiment_id: str
    metric_name: str
    baseline_value: float
    observed_value: float
    tolerance_pct: float = 10.0


@router.post("/experiments")
async def create_experiment(
    body: CreateExperimentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    experiment = tracker.create_experiment(**body.model_dump())
    return experiment.model_dump()


@router.get("/experiments")
async def list_experiments(
    status: str | None = None,
    target_service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        e.model_dump()
        for e in tracker.list_experiments(status=status, target_service=target_service)
    ]


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    experiment = tracker.get_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")
    return experiment.model_dump()


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(
    experiment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    removed = tracker.delete_experiment(experiment_id)
    if not removed:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")
    return {"deleted": True, "experiment_id": experiment_id}


@router.put("/experiments/{experiment_id}/start")
async def start_experiment(
    experiment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    experiment = tracker.start_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")
    return experiment.model_dump()


@router.put("/experiments/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: str,
    body: CompleteExperimentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    experiment = tracker.complete_experiment(experiment_id, **body.model_dump())
    return experiment.model_dump()


@router.put("/experiments/{experiment_id}/abort")
async def abort_experiment(
    experiment_id: str,
    body: AbortExperimentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    experiment = tracker.abort_experiment(experiment_id, **body.model_dump())
    if experiment is None:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")
    return experiment.model_dump()


@router.post("/results")
async def record_result(
    body: RecordResultRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    result = tracker.record_result(**body.model_dump())
    return result.model_dump()


@router.get("/results/{experiment_id}")
async def get_results(
    experiment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [r.model_dump() for r in tracker.get_results(experiment_id)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
