"""Chaos experiment designer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/chaos-designer", tags=["Chaos Designer"])

_designer: Any = None


def set_designer(designer: Any) -> None:
    global _designer
    _designer = designer


def _get_designer() -> Any:
    if _designer is None:
        raise HTTPException(503, "Chaos designer service unavailable")
    return _designer


class CreateExperimentRequest(BaseModel):
    name: str
    experiment_type: str = "NETWORK_PARTITION"
    target_service: str = ""
    hypothesis: str = ""
    blast_radius_level: str = "MINIMAL"
    rollback_plan: str = ""
    prerequisites: list[str] = []
    affected_services: list[str] = []
    estimated_duration_minutes: int = 30


@router.post("/experiments")
async def create_experiment(
    body: CreateExperimentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    exp = designer.create_experiment(**body.model_dump())
    return exp.model_dump()


@router.get("/experiments")
async def list_experiments(
    experiment_type: str | None = None,
    status: str | None = None,
    target_service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    designer = _get_designer()
    return [
        e.model_dump()
        for e in designer.list_experiments(
            experiment_type=experiment_type,
            status=status,
            target_service=target_service,
            limit=limit,
        )
    ]


@router.get("/experiments/{exp_id}")
async def get_experiment(
    exp_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    exp = designer.get_experiment(exp_id)
    if exp is None:
        raise HTTPException(404, f"Experiment '{exp_id}' not found")
    return exp.model_dump()


@router.post("/experiments/{exp_id}/blast-radius")
async def estimate_blast_radius(
    exp_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    result = designer.estimate_blast_radius(exp_id)
    if not result:
        raise HTTPException(404, f"Experiment '{exp_id}' not found")
    return result


@router.post("/experiments/{exp_id}/validate")
async def validate_prerequisites(
    exp_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    designer = _get_designer()
    checks = designer.validate_prerequisites(exp_id)
    return [c.model_dump() for c in checks]


@router.post("/experiments/{exp_id}/rollback-plan")
async def generate_rollback_plan(
    exp_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    result = designer.generate_rollback_plan(exp_id)
    if not result:
        raise HTTPException(404, f"Experiment '{exp_id}' not found")
    return result


@router.post("/experiments/{exp_id}/approve")
async def approve_experiment(
    exp_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    exp = designer.approve_experiment(exp_id)
    if exp is None:
        raise HTTPException(404, f"Experiment '{exp_id}' not found or not in DRAFT status")
    return exp.model_dump()


@router.get("/coverage")
async def analyze_experiment_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    return designer.analyze_experiment_coverage()


@router.get("/report")
async def generate_design_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    return designer.generate_design_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    designer = _get_designer()
    return designer.get_stats()
