"""Reliability regression detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.reliability_regression import (
    CorrelationStrength,
    RegressionSeverity,
    RegressionType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/reliability-regression",
    tags=["Reliability Regression"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Reliability regression service unavailable")
    return _engine


class RecordRegressionRequest(BaseModel):
    service: str
    change_id: str = ""
    regression_type: RegressionType = RegressionType.ERROR_RATE
    baseline_value: float = 0.0
    current_value: float = 0.0
    deviation_pct: float = 0.0
    correlation: CorrelationStrength = CorrelationStrength.UNKNOWN
    details: str = ""


@router.post("/regressions")
async def record_regression(
    body: RecordRegressionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_regression(**body.model_dump())
    return result.model_dump()


@router.get("/regressions")
async def list_regressions(
    service: str | None = None,
    regression_type: RegressionType | None = None,
    severity: RegressionSeverity | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_regressions(
            service=service, regression_type=regression_type, severity=severity, limit=limit
        )
    ]


@router.get("/regressions/{record_id}")
async def get_regression(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_regression(record_id)
    if result is None:
        raise HTTPException(404, f"Regression '{record_id}' not found")
    return result.model_dump()


@router.get("/by-change/{change_id}")
async def detect_regressions_for_change(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_regressions_for_change(change_id)


@router.get("/service/{service}")
async def analyze_service_regressions(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_regressions(service)


@router.get("/prone-services")
async def identify_regression_prone_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_regression_prone_services()


@router.get("/correlations")
async def correlate_with_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.correlate_with_changes()


@router.get("/rate")
async def calculate_regression_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_regression_rate()


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


rr_route = router
