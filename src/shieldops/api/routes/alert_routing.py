"""Alert routing optimization API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/alert-routing", tags=["Alert Routing"])

_optimizer: Any = None


def set_optimizer(optimizer: Any) -> None:
    global _optimizer
    _optimizer = optimizer


def _get_optimizer() -> Any:
    if _optimizer is None:
        raise HTTPException(503, "Alert routing service unavailable")
    return _optimizer


class RecordRoutingRequest(BaseModel):
    alert_id: str = ""
    alert_type: str = ""
    team: str = ""
    channel: str = "SLACK"
    action_taken: str = "acknowledged"
    response_time_seconds: float = 0.0
    was_rerouted: bool = False


@router.post("/routings")
async def record_routing(
    body: RecordRoutingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    routing = optimizer.record_routing(**body.model_dump())
    return routing.model_dump()


@router.get("/routings")
async def list_routings(
    team: str | None = None,
    channel: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        r.model_dump() for r in optimizer.list_routings(team=team, channel=channel, limit=limit)
    ]


@router.get("/routings/{routing_id}")
async def get_routing(
    routing_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    routing = optimizer.get_routing(routing_id)
    if routing is None:
        raise HTTPException(404, f"Routing '{routing_id}' not found")
    return routing.model_dump()


@router.post("/recommendations/generate")
async def generate_recommendations(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [r.model_dump() for r in optimizer.generate_recommendations()]


@router.get("/team-effectiveness")
async def analyze_team_effectiveness(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.analyze_team_effectiveness(team=team)


@router.get("/reroute-patterns")
async def detect_reroute_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [p.model_dump() for p in optimizer.detect_reroute_patterns()]


@router.get("/channel-effectiveness")
async def compute_channel_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.compute_channel_effectiveness()


@router.get("/ignored")
async def identify_ignored_alerts(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [a.model_dump() for a in optimizer.identify_ignored_alerts(limit=limit)]


@router.get("/analysis-report")
async def generate_analysis_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.generate_analysis_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.get_stats()
