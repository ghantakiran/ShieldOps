"""Config Drift Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.config_drift_monitor import (
    DriftSeverity,
    DriftSource,
    DriftType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/config-drift-monitor",
    tags=["Config Drift Monitor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Config drift monitor service unavailable",
        )
    return _engine


class RecordDriftRequest(BaseModel):
    model_config = {"extra": "forbid"}

    resource_id: str
    drift_type: DriftType = DriftType.PARAMETER_CHANGE
    severity: DriftSeverity = DriftSeverity.MODERATE
    source: DriftSource = DriftSource.UNKNOWN
    expected_value: str = ""
    actual_value: str = ""
    environment: str = ""
    team: str = ""


class AddResolutionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    drift_id: str
    resolved_by: str
    resolution_method: str
    resolution_time_minutes: float


@router.post("/records")
async def record_drift(
    body: RecordDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_drift(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_drifts(
    drift_type: DriftType | None = None,
    severity: DriftSeverity | None = None,
    environment: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_drifts(
            drift_type=drift_type,
            severity=severity,
            environment=environment,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_drift(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_drift(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Drift record '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/resolutions")
async def add_resolution(
    body: AddResolutionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    resolution = engine.add_resolution(**body.model_dump())
    return resolution.model_dump()


@router.get("/by-environment")
async def analyze_drift_by_environment(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_drift_by_environment()


@router.get("/critical")
async def identify_critical_drifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_drifts()


@router.get("/rank-by-severity")
async def rank_by_severity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_severity()


@router.get("/trends")
async def detect_drift_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_drift_trends()


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


cdm_route = router
