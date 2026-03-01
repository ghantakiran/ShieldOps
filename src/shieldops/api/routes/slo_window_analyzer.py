"""SLO Window Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_window_analyzer import (
    ComplianceStatus,
    WindowDuration,
    WindowStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-window",
    tags=["SLO Window"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO window service unavailable")
    return _engine


class RecordWindowRequest(BaseModel):
    slo_id: str
    window_duration: WindowDuration = WindowDuration.MONTHLY
    compliance_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    window_strategy: WindowStrategy = WindowStrategy.ROLLING
    compliance_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddEvaluationRequest(BaseModel):
    slo_id: str
    window_duration: WindowDuration = WindowDuration.MONTHLY
    eval_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/windows")
async def record_window(
    body: RecordWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_window(**body.model_dump())
    return result.model_dump()


@router.get("/windows")
async def list_windows(
    duration: WindowDuration | None = None,
    status: ComplianceStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_windows(
            duration=duration,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/windows/{record_id}")
async def get_window(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_window(record_id)
    if result is None:
        raise HTTPException(404, f"Window record '{record_id}' not found")
    return result.model_dump()


@router.post("/evaluations")
async def add_evaluation(
    body: AddEvaluationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_evaluation(**body.model_dump())
    return result.model_dump()


@router.get("/compliance")
async def analyze_window_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_window_compliance()


@router.get("/breaching")
async def identify_breaching_windows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_breaching_windows()


@router.get("/compliance-rankings")
async def rank_by_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance()


@router.get("/trends")
async def detect_compliance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_compliance_trends()


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


swa_route = router
