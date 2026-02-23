"""Threshold tuning API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/threshold-tuner",
    tags=["Threshold Tuner"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Threshold tuner service unavailable")
    return _engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterThresholdRequest(BaseModel):
    metric_name: str
    current_value: float
    direction: str = "upper"
    service: str = ""
    min_value: float = 0.0
    max_value: float = 100.0


class RecordSampleRequest(BaseModel):
    threshold_id: str
    value: float
    triggered_alert: bool = False
    was_actionable: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/thresholds")
async def register_threshold(
    body: RegisterThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    config = engine.register_threshold(
        metric_name=body.metric_name,
        current_value=body.current_value,
        direction=body.direction,
        service=body.service,
        min_value=body.min_value,
        max_value=body.max_value,
    )
    return config.model_dump()


@router.get("/thresholds")
async def list_thresholds(
    direction: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    thresholds = engine.list_thresholds(direction=direction)
    return [t.model_dump() for t in thresholds[-limit:]]


@router.get("/thresholds/{threshold_id}")
async def get_threshold(
    threshold_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    config = engine.get_threshold(threshold_id)
    if config is None:
        raise HTTPException(404, f"Threshold '{threshold_id}' not found")
    return config.model_dump()


@router.post("/samples")
async def record_sample(
    body: RecordSampleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    sample = engine.record_sample(
        threshold_id=body.threshold_id,
        value=body.value,
        triggered_alert=body.triggered_alert,
        was_actionable=body.was_actionable,
    )
    if sample is None:
        raise HTTPException(404, f"Threshold '{body.threshold_id}' not found")
    return sample.model_dump()


@router.post("/recommendations/generate")
async def generate_recommendations(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    recs = engine.generate_recommendations()
    return [r.model_dump() for r in recs]


@router.get("/recommendations")
async def list_recommendations(
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    recs = engine.list_recommendations(status=status)
    return [r.model_dump() for r in recs[-limit:]]


@router.put("/recommendations/{recommendation_id}/apply")
async def apply_recommendation(
    recommendation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.apply_recommendation(recommendation_id)
    if rec is None:
        raise HTTPException(404, f"Recommendation '{recommendation_id}' not found")
    return rec.model_dump()


@router.put("/recommendations/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.reject_recommendation(recommendation_id)
    if rec is None:
        raise HTTPException(404, f"Recommendation '{recommendation_id}' not found")
    return rec.model_dump()


@router.delete("/thresholds/{threshold_id}")
async def delete_threshold(
    threshold_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    deleted = engine.delete_threshold(threshold_id)
    if not deleted:
        raise HTTPException(404, f"Threshold '{threshold_id}' not found")
    return {"deleted": True, "threshold_id": threshold_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
