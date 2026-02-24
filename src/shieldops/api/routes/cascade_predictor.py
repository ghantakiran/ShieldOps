"""Cascading failure predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cascade-predictor", tags=["Cascade Predictor"])

_predictor: Any = None


def set_predictor(predictor: Any) -> None:
    global _predictor
    _predictor = predictor


def _get_predictor() -> Any:
    if _predictor is None:
        raise HTTPException(503, "Cascade predictor service unavailable")
    return _predictor


class RegisterServiceRequest(BaseModel):
    service_name: str
    dependencies: list[str] | None = None
    failure_type: str = "LATENCY_SPIKE"
    propagation_mode: str = "SEQUENTIAL"
    criticality_score: float = 0.0


@router.post("/services")
async def register_service(
    body: RegisterServiceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    service = predictor.register_service(**body.model_dump())
    return service.model_dump()


@router.get("/services")
async def list_services(
    failure_type: str | None = None,
    propagation_mode: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return [
        s.model_dump()
        for s in predictor.list_services(
            failure_type=failure_type, propagation_mode=propagation_mode, limit=limit
        )
    ]


@router.get("/services/{service_id}")
async def get_service(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    service = predictor.get_service(service_id)
    if service is None:
        raise HTTPException(404, f"Service '{service_id}' not found")
    return service.model_dump()


@router.post("/predict/{source_service_id}")
async def predict_cascade(
    source_service_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    prediction = predictor.predict_cascade(source_service_id)
    return prediction.model_dump()


@router.get("/critical-paths")
async def identify_critical_paths(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return predictor.identify_critical_paths()


@router.get("/blast-radius/{service_id}")
async def calculate_blast_radius(
    service_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.calculate_blast_radius(service_id)


@router.get("/single-points-of-failure")
async def detect_single_points_of_failure(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return [s.model_dump() for s in predictor.detect_single_points_of_failure()]


@router.get("/risk-ranking")
async def rank_services_by_cascade_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return predictor.rank_services_by_cascade_risk()


@router.get("/report")
async def generate_cascade_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.generate_cascade_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.get_stats()
