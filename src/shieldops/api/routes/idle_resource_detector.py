"""Idle Resource Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.idle_resource_detector import (
    IdleClassification,
    ResourceCategory,
)

logger = structlog.get_logger()
ird_route = APIRouter(
    prefix="/idle-resource-detector",
    tags=["Idle Resource Detector"],
)

_detector: Any = None


def set_detector(detector: Any) -> None:
    global _detector
    _detector = detector


def _get_detector() -> Any:
    if _detector is None:
        raise HTTPException(503, "Idle resource detector unavailable")
    return _detector


class RecordResourceRequest(BaseModel):
    resource_id: str
    resource_name: str
    category: ResourceCategory
    utilization_pct: float
    cost_per_hour: float
    idle_hours: float = 0.0
    team: str = ""
    last_active_at: float = 0.0


@ird_route.post("/resources")
async def record_resource(
    body: RecordResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    record = detector.record_resource(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@ird_route.get("/resources")
async def list_resources(
    category: ResourceCategory | None = None,
    classification: IdleClassification | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in detector.list_resources(
            category=category,
            classification=classification,
            limit=limit,
        )
    ]


@ird_route.get("/resources/{record_id}")
async def get_resource(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    record = detector.get_resource(record_id)
    if record is None:
        raise HTTPException(404, f"Resource '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@ird_route.post("/resources/{record_id}/recommend")
async def recommend_action(
    record_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.recommend_action(record_id)  # type: ignore[no-any-return]


@ird_route.get("/wasted-cost")
async def calculate_wasted_cost(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.calculate_wasted_cost()  # type: ignore[no-any-return]


@ird_route.get("/team-summary")
async def summarize_by_team(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    summaries = detector.summarize_by_team()
    return [s.model_dump() for s in summaries]  # type: ignore[no-any-return]


@ird_route.get("/rank")
async def rank_by_waste(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return detector.rank_by_waste()  # type: ignore[no-any-return]


@ird_route.get("/report")
async def generate_idle_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.generate_idle_report().model_dump()  # type: ignore[no-any-return]


@ird_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.get_stats()  # type: ignore[no-any-return]


@ird_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    detector = _get_detector()
    detector.clear_data()
    return {"status": "cleared"}
