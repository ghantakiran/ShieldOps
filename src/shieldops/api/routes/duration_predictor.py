"""Duration predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.duration_predictor import (
    IncidentComplexity,
    ResolutionPath,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/duration-predictor",
    tags=["Duration Predictor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Duration predictor service unavailable",
        )
    return _engine


class RecordPredictionRequest(BaseModel):
    incident_id: str
    service_name: str
    severity: str
    complexity: IncidentComplexity
    resolution_path: ResolutionPath
    responder_count: int = 1
    is_business_hours: bool = True


class PredictDurationRequest(BaseModel):
    complexity: IncidentComplexity
    resolution_path: ResolutionPath
    responder_count: int = 1
    is_business_hours: bool = True


class RecordActualRequest(BaseModel):
    actual_minutes: float


@router.post("/records")
async def record_prediction(
    body: RecordPredictionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_prediction(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_predictions(
    service_name: str | None = None,
    complexity: IncidentComplexity | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_predictions(
            service_name=service_name,
            complexity=complexity,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_prediction(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_prediction(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()


@router.post("/predict")
async def predict_duration(
    body: PredictDurationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.predict_duration(**body.model_dump())


@router.post("/records/{record_id}/actual")
async def record_actual_duration(
    record_id: str,
    body: RecordActualRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_actual_duration(record_id, body.actual_minutes)
    if result.get("error"):
        raise HTTPException(404, f"Record '{record_id}' not found")
    return result


@router.get("/accuracy")
async def get_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_accuracy()


@router.get("/benchmarks")
async def get_benchmarks(
    service_name: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compute_benchmarks(service_name=service_name).model_dump()


@router.get("/slow-services")
async def get_slow_services(
    threshold_minutes: float = 60.0,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_resolving_services(
        threshold_minutes=threshold_minutes,
    )


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_duration_report()
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


dp_route = router
