"""Deployment cadence API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deployment-cadence",
    tags=["Deployment Cadence"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(
            503,
            "Deployment cadence service unavailable",
        )
    return _analyzer


# -- Request models -------------------------------------------------


class RecordDeploymentRequest(BaseModel):
    service_name: str
    team: str = ""
    time_slot: str = "business_hours"
    frequency: str = "weekly"
    environment: str = "production"
    is_success: bool = True
    rollback: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# -- Routes ---------------------------------------------------------


@router.post("/deployments")
async def record_deployment(
    body: RecordDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    event = analyzer.record_deployment(**body.model_dump())
    return event.model_dump()


@router.get("/deployments/{event_id}")
async def get_deployment(
    event_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    event = analyzer.get_deployment(event_id)
    if event is None:
        raise HTTPException(
            404,
            f"Deployment '{event_id}' not found",
        )
    return event.model_dump()


@router.get("/deployments")
async def list_deployments(
    service_name: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    items = analyzer.list_deployments(
        service_name=service_name,
        team=team,
        limit=limit,
    )
    return [e.model_dump() for e in items]


@router.get("/cadence/{service_name}")
async def calculate_cadence(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    score = analyzer.calculate_cadence(service_name)
    return score.model_dump()


@router.get("/health")
async def detect_cadence_health(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [s.model_dump() for s in analyzer.detect_cadence_health()]


@router.get("/bottlenecks")
async def identify_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.identify_bottlenecks()


@router.get("/time-distribution")
async def analyze_time_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, int]:
    analyzer = _get_analyzer()
    return analyzer.analyze_time_distribution()


@router.get("/compare-teams")
async def compare_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.compare_teams()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_cadence_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
