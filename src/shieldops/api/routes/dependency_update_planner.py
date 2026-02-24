"""Dependency update planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-update-planner",
    tags=["Dependency Update Planner"],
)

_planner: Any = None


def set_planner(planner: Any) -> None:
    global _planner
    _planner = planner


def _get_planner() -> Any:
    if _planner is None:
        raise HTTPException(
            503,
            "Dependency update planner service unavailable",
        )
    return _planner


# -- Request models -------------------------------------------------


class RegisterUpdateRequest(BaseModel):
    package_name: str
    current_version: str = ""
    target_version: str = ""
    risk: str = "LOW"
    strategy: str = "IMMEDIATE"
    dependents: list[str] = []
    test_coverage_pct: float = 0.0
    breaking_changes: list[str] = []


class CreatePlanRequest(BaseModel):
    name: str
    update_ids: list[str] = []


# -- Routes ---------------------------------------------------------


@router.post("/updates")
async def register_update(
    body: RegisterUpdateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    upd = planner.register_update(**body.model_dump())
    return upd.model_dump()


@router.get("/updates")
async def list_updates(
    risk: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return [u.model_dump() for u in planner.list_updates(risk=risk, status=status, limit=limit)]


@router.get("/updates/{update_id}")
async def get_update(
    update_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    upd = planner.get_update(update_id)
    if upd is None:
        raise HTTPException(404, f"Update '{update_id}' not found")
    return upd.model_dump()


@router.post("/plans")
async def create_plan(
    body: CreatePlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    plan = planner.create_plan(**body.model_dump())
    return plan.model_dump()


@router.post("/plans/{plan_id}/execution-order")
async def calculate_execution_order(
    plan_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[str]:
    planner = _get_planner()
    return planner.calculate_execution_order(plan_id)


@router.get("/updates/{update_id}/risk")
async def assess_update_risk(
    update_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.assess_update_risk(update_id)


@router.get("/breaking-chains")
async def detect_breaking_chains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return planner.detect_breaking_chains()


@router.get("/plans/{plan_id}/duration")
async def estimate_plan_duration(
    plan_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    hours = planner.estimate_plan_duration(plan_id)
    return {"plan_id": plan_id, "hours": hours}


@router.get("/report")
async def generate_planner_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.generate_planner_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.get_stats()
