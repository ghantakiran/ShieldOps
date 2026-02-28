"""Dynamic risk scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.dynamic_risk_scorer import (
    RiskFactor,
    ScoreAdjustment,
    ScoringModel,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dynamic-risk-scorer",
    tags=["Dynamic Risk Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dynamic risk scorer service unavailable")
    return _engine


class RecordScoreRequest(BaseModel):
    service_name: str
    risk_factor: RiskFactor = RiskFactor.INCIDENT_FREQUENCY
    score_adjustment: ScoreAdjustment = ScoreAdjustment.STABLE
    scoring_model: ScoringModel = ScoringModel.LINEAR
    risk_score: float = 0.0
    details: str = ""


class AddAdjustmentRequest(BaseModel):
    event_label: str
    risk_factor: RiskFactor = RiskFactor.INCIDENT_FREQUENCY
    score_adjustment: ScoreAdjustment = ScoreAdjustment.INCREASE
    magnitude: float = 0.0


@router.post("/scores")
async def record_score(
    body: RecordScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_score(**body.model_dump())
    return result.model_dump()


@router.get("/scores")
async def list_scores(
    service_name: str | None = None,
    risk_factor: RiskFactor | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scores(
            service_name=service_name,
            risk_factor=risk_factor,
            limit=limit,
        )
    ]


@router.get("/scores/{record_id}")
async def get_score(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_score(record_id)
    if result is None:
        raise HTTPException(404, f"Score '{record_id}' not found")
    return result.model_dump()


@router.post("/adjustments")
async def add_adjustment(
    body: AddAdjustmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_adjustment(**body.model_dump())
    return result.model_dump()


@router.get("/risk-trajectory/{service_name}")
async def analyze_risk_trajectory(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_risk_trajectory(service_name)


@router.get("/high-risk-services")
async def identify_high_risk_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_services()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/risk-spikes")
async def detect_risk_spikes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_risk_spikes()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


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


drs_route = router
