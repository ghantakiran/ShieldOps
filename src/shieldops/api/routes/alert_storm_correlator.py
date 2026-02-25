"""Alert storm correlator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_storm_correlator import (
    CorrelationMethod,
    StormPhase,
    StormSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-storm-correlator",
    tags=["Alert Storm Correlator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Alert storm correlator service unavailable",
        )
    return _engine


class RecordStormRequest(BaseModel):
    storm_name: str
    severity: StormSeverity = StormSeverity.MINOR
    method: CorrelationMethod = CorrelationMethod.TEMPORAL


class DetectStormRequest(BaseModel):
    alerts: list[dict[str, Any]]


class AddAlertRequest(BaseModel):
    alert_name: str
    service: str
    severity: str = "warning"


class UpdatePhaseRequest(BaseModel):
    phase: StormPhase


@router.post("/storms")
async def record_storm(
    body: RecordStormRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    storm = engine.record_storm(**body.model_dump())
    return storm.model_dump()


@router.get("/storms")
async def list_storms(
    severity: StormSeverity | None = None,
    phase: StormPhase | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_storms(
            severity=severity,
            phase=phase,
            limit=limit,
        )
    ]


@router.get("/storms/{storm_id}")
async def get_storm(
    storm_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    storm = engine.get_storm(storm_id)
    if storm is None:
        raise HTTPException(404, f"Storm '{storm_id}' not found")
    return storm.model_dump()


@router.post("/detect")
async def detect_storm(
    body: DetectStormRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_storm(body.alerts)


@router.post("/storms/{storm_id}/alerts")
async def add_alert_to_storm(
    storm_id: str,
    body: AddAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_alert_to_storm(
        storm_id,
        alert_name=body.alert_name,
        service=body.service,
        severity=body.severity,
    )
    if result.get("error"):
        raise HTTPException(404, f"Storm '{storm_id}' not found")
    return result


@router.get("/storms/{storm_id}/root-cause")
async def identify_root_cause(
    storm_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.identify_root_cause(storm_id)
    if result.get("error"):
        raise HTTPException(404, f"Storm '{storm_id}' not found")
    return result


@router.get("/frequency")
async def calculate_storm_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_storm_frequency()


@router.post("/storms/{storm_id}/phase")
async def update_storm_phase(
    storm_id: str,
    body: UpdatePhaseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.update_storm_phase(storm_id, body.phase)
    if result.get("error"):
        raise HTTPException(404, f"Storm '{storm_id}' not found")
    return result


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_storm_report()
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


asc_route = router
