"""Commitment planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/commitment-planner", tags=["Commitment Planner"])

_planner: Any = None


def set_planner(planner: Any) -> None:
    global _planner
    _planner = planner


def _get_planner() -> Any:
    if _planner is None:
        raise HTTPException(503, "Commitment planner service unavailable")
    return _planner


class RegisterWorkloadRequest(BaseModel):
    service_name: str
    current_pricing: str = "ON_DEMAND"
    pattern: str = "STEADY_STATE"
    monthly_cost: float = 0.0
    avg_utilization_pct: float = 0.0
    peak_utilization_pct: float = 0.0


@router.post("/workloads")
async def register_workload(
    body: RegisterWorkloadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    workload = planner.register_workload(**body.model_dump())
    return workload.model_dump()


@router.get("/workloads")
async def list_workloads(
    pattern: str | None = None,
    current_pricing: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return [
        w.model_dump()
        for w in planner.list_workloads(
            pattern=pattern, current_pricing=current_pricing, limit=limit
        )
    ]


@router.get("/workloads/{wl_id}")
async def get_workload(
    wl_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    workload = planner.get_workload(wl_id)
    if workload is None:
        raise HTTPException(404, f"Workload '{wl_id}' not found")
    return workload.model_dump()


@router.post("/workloads/{wl_id}/recommend")
async def recommend_pricing_model(
    wl_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    recommendation = planner.recommend_pricing_model(wl_id)
    if recommendation is None:
        raise HTTPException(404, f"Workload '{wl_id}' not found")
    return recommendation.model_dump()


@router.post("/optimal-mix")
async def calculate_optimal_mix(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    result = planner.calculate_optimal_mix()
    return result.model_dump()


@router.post("/workloads/{wl_id}/savings")
async def estimate_savings(
    wl_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    result = planner.estimate_savings(wl_id)
    return result.model_dump()


@router.post("/workloads/{wl_id}/detect-pattern")
async def detect_workload_pattern(
    wl_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    result = planner.detect_workload_pattern(wl_id)
    return result.model_dump()


@router.post("/workloads/{wl_id}/compare")
async def compare_commitment_scenarios(
    wl_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    result = planner.compare_commitment_scenarios(wl_id)
    return result.model_dump()


@router.get("/report")
async def generate_plan_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.generate_plan_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.get_stats()
