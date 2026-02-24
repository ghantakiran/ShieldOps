"""Metric baseline API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/metric-baseline",
    tags=["Metric Baseline"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(
            503,
            "Metric baseline service unavailable",
        )
    return _manager


# -- Request models -------------------------------------------------


class CreateBaselineRequest(BaseModel):
    service_name: str
    metric_name: str
    metric_type: str = "latency"
    strategy: str = "static"
    baseline_value: float = 0.0
    upper_bound: float = 0.0
    lower_bound: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordMetricRequest(BaseModel):
    value: float


# -- Routes ---------------------------------------------------------


@router.post("/baselines")
async def create_baseline(
    body: CreateBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    bl = manager.create_baseline(**body.model_dump())
    return bl.model_dump()


@router.get("/baselines/{baseline_id}")
async def get_baseline(
    baseline_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    bl = manager.get_baseline(baseline_id)
    if bl is None:
        raise HTTPException(
            404,
            f"Baseline '{baseline_id}' not found",
        )
    return bl.model_dump()


@router.get("/baselines")
async def list_baselines(
    service_name: str | None = None,
    metric_type: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    items = manager.list_baselines(
        service_name=service_name,
        metric_type=metric_type,
        limit=limit,
    )
    return [b.model_dump() for b in items]


@router.post("/baselines/{baseline_id}/record")
async def record_metric_value(
    baseline_id: str,
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    dev = manager.record_metric_value(
        baseline_id,
        body.value,
    )
    if dev is None:
        raise HTTPException(
            404,
            f"Baseline '{baseline_id}' not found",
        )
    return dev.model_dump()


@router.get("/baselines/{baseline_id}/detect")
async def detect_deviation(
    baseline_id: str,
    value: float = 0.0,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    dev = manager.detect_deviation(baseline_id, value)
    if dev is None:
        raise HTTPException(
            404,
            f"Baseline '{baseline_id}' not found",
        )
    return dev.model_dump()


@router.post("/baselines/{baseline_id}/auto-update")
async def auto_update_baseline(
    baseline_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    bl = manager.auto_update_baseline(baseline_id)
    if bl is None:
        raise HTTPException(
            404,
            f"Baseline '{baseline_id}' not found",
        )
    return bl.model_dump()


@router.get("/stale")
async def identify_stale_baselines(
    max_age_hours: int = 168,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    stale = manager.identify_stale_baselines(max_age_hours)
    return [b.model_dump() for b in stale]


@router.get("/accuracy")
async def calculate_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return manager.calculate_baseline_accuracy()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.generate_baseline_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_stats()
