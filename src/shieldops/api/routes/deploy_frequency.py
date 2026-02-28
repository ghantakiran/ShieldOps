"""Deployment frequency analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_frequency import (
    DeploymentType,
    FrequencyBand,
    FrequencyTrend,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deploy-frequency",
    tags=["Deploy Frequency"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Deployment frequency service unavailable",
        )
    return _engine


class RecordFrequencyRequest(BaseModel):
    service: str
    team: str = ""
    deployment_type: DeploymentType = DeploymentType.FEATURE
    frequency_band: FrequencyBand = FrequencyBand.MEDIUM
    deploys_per_week: float = 0.0
    deploy_success_rate: float = 100.0
    lead_time_hours: float = 0.0
    details: str = ""


class AddMetricRequest(BaseModel):
    metric_name: str
    service: str = ""
    team: str = ""
    value: float = 0.0
    unit: str = ""
    trend: FrequencyTrend = FrequencyTrend.STABLE
    description: str = ""


@router.post("/records")
async def record_frequency(
    body: RecordFrequencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_frequency(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_frequencies(
    frequency_band: FrequencyBand | None = None,
    deployment_type: DeploymentType | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_frequencies(
            frequency_band=frequency_band,
            deployment_type=deployment_type,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_frequency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_frequency(record_id)
    if record is None:
        raise HTTPException(404, f"Frequency record '{record_id}' not found")
    return record.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    metric = engine.add_metric(**body.model_dump())
    return metric.model_dump()


@router.get("/by-team")
async def analyze_frequency_by_team(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_frequency_by_team()


@router.get("/low-frequency")
async def identify_low_frequency_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_frequency_services()


@router.get("/rank-by-rate")
async def rank_by_deploy_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_deploy_rate()


@router.get("/trends")
async def detect_frequency_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_frequency_trends()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
    return report.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


dfa_route = router
