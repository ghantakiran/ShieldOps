"""Incident recurrence predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
rp_route = APIRouter(
    prefix="/recurrence-predictor",
    tags=["Recurrence Predictor"],
)

_instance: Any = None


def set_predictor(predictor: Any) -> None:
    global _instance
    _instance = predictor


def _get_predictor() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Recurrence predictor service unavailable",
        )
    return _instance


# -- Request models --


class RecordIncidentRequest(BaseModel):
    incident_id: str
    service_name: str = ""
    root_cause: str = ""
    fix_completeness: str = "unresolved"
    similarity_score: float = 0.0
    predicted_recurrence_days: int = 0


class PredictRecurrenceRequest(BaseModel):
    record_id: str


class MarkRecurredRequest(BaseModel):
    record_id: str


# -- Routes --


@rp_route.post("/records")
async def record_incident(
    body: RecordIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    record = predictor.record_incident(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@rp_route.get("/records")
async def list_records(
    service_name: str | None = None,
    recurrence_risk: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in predictor.list_records(
            service_name=service_name,
            recurrence_risk=recurrence_risk,
            limit=limit,
        )
    ]


@rp_route.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    record = predictor.get_record(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{record_id}' not found",
        )
    return record.model_dump()  # type: ignore[no-any-return]


@rp_route.post("/predict")
async def predict_recurrence(
    body: PredictRecurrenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    result = predictor.predict_recurrence(
        body.record_id,
    )
    if result is None:
        raise HTTPException(
            404,
            f"Record '{body.record_id}' not found",
        )
    return result  # type: ignore[no-any-return]


@rp_route.get("/patterns")
async def get_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return [  # type: ignore[no-any-return]
        p.model_dump() for p in predictor.detect_patterns()
    ]


@rp_route.post("/mark-recurred")
async def mark_recurred(
    body: MarkRecurredRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    record = predictor.mark_recurred(body.record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{body.record_id}' not found",
        )
    return record.model_dump()  # type: ignore[no-any-return]


@rp_route.get("/accuracy")
async def get_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return {  # type: ignore[no-any-return]
        "prediction_accuracy_pct": (predictor.calculate_prediction_accuracy()),
    }


@rp_route.get("/chronic")
async def get_chronic_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return predictor.identify_chronic_incidents()  # type: ignore[no-any-return]


@rp_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    report = predictor.generate_recurrence_report()
    return report.model_dump()  # type: ignore[no-any-return]


@rp_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.get_stats()  # type: ignore[no-any-return]
