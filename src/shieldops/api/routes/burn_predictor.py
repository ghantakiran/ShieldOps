"""SLO burn rate predictor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/burn-predictor",
    tags=["Burn Predictor"],
)

_predictor: Any = None


def set_predictor(predictor: Any) -> None:
    global _predictor
    _predictor = predictor


def _get_predictor() -> Any:
    if _predictor is None:
        raise HTTPException(503, "Burn predictor service unavailable")
    return _predictor


class RegisterSLORequest(BaseModel):
    name: str
    service: str = ""
    target_pct: float = 99.9
    window_days: int = 30


class RecordErrorRequest(BaseModel):
    slo_id: str
    error_count: int = 1
    total_count: int = 1


class CorrelateDeploymentRequest(BaseModel):
    slo_id: str
    deployment_time: float
    deployment_id: str = ""


@router.post("/slos")
async def register_slo(
    body: RegisterSLORequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    slo = predictor.register_slo(
        name=body.name,
        service=body.service,
        target_pct=body.target_pct,
        window_days=body.window_days,
    )
    return slo.model_dump()


@router.get("/slos")
async def list_slos(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    slos = predictor.list_slos(service=service, limit=limit)
    return [s.model_dump() for s in slos]


@router.get("/slos/{slo_id}")
async def get_slo(
    slo_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    slo = predictor.get_slo(slo_id)
    if slo is None:
        raise HTTPException(404, f"SLO '{slo_id}' not found")
    return slo.model_dump()


@router.post("/errors")
async def record_error_event(
    body: RecordErrorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.record_error_event(
        slo_id=body.slo_id,
        error_count=body.error_count,
        total_count=body.total_count,
    )


@router.get("/predict/{slo_id}")
async def predict_burn(
    slo_id: str,
    horizon: str = "one_day",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    prediction = predictor.predict_burn(slo_id, horizon=horizon)
    if prediction is None:
        raise HTTPException(404, f"SLO '{slo_id}' not found")
    return prediction.model_dump()


@router.get("/forecast/{slo_id}")
async def forecast_violation(
    slo_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    forecast = predictor.forecast_violation(slo_id)
    if forecast is None:
        raise HTTPException(404, f"SLO '{slo_id}' not found")
    return forecast.model_dump()


@router.get("/budget/{slo_id}")
async def get_budget_status(
    slo_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    status = predictor.get_budget_status(slo_id)
    if status is None:
        raise HTTPException(404, f"SLO '{slo_id}' not found")
    return status


@router.post("/correlate-deployment")
async def correlate_deployments(
    body: CorrelateDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.correlate_deployments(
        slo_id=body.slo_id,
        deployment_time=body.deployment_time,
        deployment_id=body.deployment_id,
    )


@router.get("/breach-risk")
async def get_breach_risk(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return predictor.get_breach_risk(limit=limit)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.get_stats()
