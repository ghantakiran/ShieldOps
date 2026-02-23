"""SRE metrics aggregation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/sre-metrics", tags=["SRE Metrics"])

_aggregator: Any = None


def set_aggregator(agg: Any) -> None:
    global _aggregator
    _aggregator = agg


def _get_aggregator() -> Any:
    if _aggregator is None:
        raise HTTPException(503, "SRE metrics service unavailable")
    return _aggregator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordMetricRequest(BaseModel):
    service: str
    category: str
    metric_name: str
    value: float
    unit: str = ""
    period: str = "hourly"


class GenerateScorecardRequest(BaseModel):
    period: str = "monthly"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/datapoints")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    dp = agg.record_metric(**body.model_dump())
    return dp.model_dump()


@router.post("/scorecards/{service}")
async def generate_scorecard(
    service: str,
    body: GenerateScorecardRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    sc = agg.generate_scorecard(service, period=body.period)
    return sc.model_dump()


@router.get("/scorecards")
async def list_scorecards(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    return [s.model_dump() for s in agg.list_scorecards()]


@router.get("/scorecards/{scorecard_id}/detail")
async def get_scorecard(
    scorecard_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    sc = agg.get_scorecard(scorecard_id)
    if sc is None:
        raise HTTPException(404, f"Scorecard '{scorecard_id}' not found")
    return sc.model_dump()


@router.get("/datapoints")
async def list_datapoints(
    service: str | None = None,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    agg = _get_aggregator()
    return [
        d.model_dump() for d in agg.list_datapoints(service=service, category=category, limit=limit)
    ]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    agg = _get_aggregator()
    return agg.get_stats()
