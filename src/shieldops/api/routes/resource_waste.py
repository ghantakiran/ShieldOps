"""Resource waste detection API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.resource_waste import (
    ResourceType,
    WasteCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/resource-waste",
    tags=["Resource Waste"],
)

_instance: Any = None


def set_detector(detector: Any) -> None:
    global _instance
    _instance = detector


def _get_detector() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Resource waste service unavailable",
        )
    return _instance


# -- Request models --


class RecordWasteRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType = ResourceType.COMPUTE
    waste_category: WasteCategory = WasteCategory.IDLE
    utilization_pct: float = 0.0
    estimated_monthly_waste: float = 0.0
    service_name: str = ""
    region: str = ""
    last_active: float = 0.0


# -- Routes --


@router.post("/records")
async def record_waste(
    body: RecordWasteRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    record = detector.record_waste(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_waste(
    resource_type: ResourceType | None = None,
    waste_category: WasteCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [
        r.model_dump()
        for r in detector.list_waste(
            resource_type=resource_type,
            waste_category=waste_category,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_waste(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    record = detector.get_waste(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{record_id}' not found",
        )
    return record.model_dump()


@router.get("/total")
async def get_total_waste(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return {
        "total_monthly_waste": (detector.calculate_total_waste()),
    }


@router.get("/ranked")
async def rank_by_cost(
    limit: int = 20,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [r.model_dump() for r in detector.rank_by_waste_cost(limit=limit)]


@router.get("/idle")
async def get_idle_resources(
    threshold_pct: float = 5.0,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [
        r.model_dump()
        for r in detector.detect_idle_resources(
            threshold_pct=threshold_pct,
        )
    ]


@router.get("/orphaned")
async def get_orphaned(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [r.model_dump() for r in detector.identify_orphaned_resources()]


@router.get("/savings")
async def get_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.estimate_savings_potential()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.generate_waste_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.get_stats()
