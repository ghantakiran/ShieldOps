"""Control Effectiveness Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.control_effectiveness import (
    ControlDomain,
    ControlType,
    EffectivenessLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/control-effectiveness", tags=["Control Effectiveness"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Control effectiveness service unavailable")
    return _engine


class RecordControlRequest(BaseModel):
    control_id: str
    control_type: ControlType = ControlType.PREVENTIVE
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.NOT_TESTED
    control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT
    effectiveness_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddTestRequest(BaseModel):
    test_name: str
    control_type: ControlType = ControlType.PREVENTIVE
    test_score: float = 0.0
    controls_tested: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_control(
    body: RecordControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_control(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_controls(
    control_type: ControlType | None = None,
    effectiveness_level: EffectivenessLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_controls(
            control_type=control_type,
            effectiveness_level=effectiveness_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_control(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_control(record_id)
    if result is None:
        raise HTTPException(404, f"Control record '{record_id}' not found")
    return result.model_dump()


@router.post("/tests")
async def add_test(
    body: AddTestRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_test(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness")
async def analyze_control_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_control_effectiveness()


@router.get("/weak-controls")
async def identify_weak_controls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weak_controls()


@router.get("/effectiveness-rankings")
async def rank_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_effectiveness()


@router.get("/trends")
async def detect_effectiveness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_effectiveness_trends()


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


cet_route = router
