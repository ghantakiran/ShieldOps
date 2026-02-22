"""API routes for capacity planning and resource forecasting."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shieldops.analytics.capacity_planner import CapacityPlanner, ResourceMetricHistory

router = APIRouter()

_planner: CapacityPlanner | None = None


def set_planner(planner: CapacityPlanner) -> None:
    global _planner
    _planner = planner


def _get_planner() -> CapacityPlanner:
    if _planner is None:
        raise HTTPException(status_code=503, detail="Capacity planner not initialized")
    return _planner


class ForecastRequest(BaseModel):
    resource_id: str
    metric_name: str
    limit: float = 100.0
    data_points: list[dict[str, Any]] = Field(default_factory=list)
    days_ahead: int = 30


@router.get("/capacity/forecasts")
async def list_forecasts() -> dict[str, Any]:
    return {"forecasts": [], "message": "Submit resources via POST /capacity/forecast"}


@router.get("/capacity/risks")
async def capacity_risks() -> dict[str, Any]:
    planner = _get_planner()
    risks = planner.detect_capacity_risks([])
    return {"risks": [r.model_dump() for r in risks], "count": len(risks)}


@router.post("/capacity/forecast")
async def forecast_resource(body: ForecastRequest) -> dict[str, Any]:
    planner = _get_planner()
    history = ResourceMetricHistory(
        resource_id=body.resource_id,
        metric_name=body.metric_name,
        limit=body.limit,
        data_points=body.data_points,
    )
    forecast = planner.forecast(history, days_ahead=body.days_ahead)
    return forecast.model_dump()
