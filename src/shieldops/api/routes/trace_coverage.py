"""Trace Coverage Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.trace_coverage import (
    CoverageGap,
    CoverageLevel,
    InstrumentationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/trace-coverage",
    tags=["Trace Coverage"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Trace coverage service unavailable")
    return _engine


class RecordCoverageRequest(BaseModel):
    service_id: str
    coverage_level: CoverageLevel = CoverageLevel.NONE
    instrumentation_type: InstrumentationType = InstrumentationType.UNINSTRUMENTED
    coverage_gap: CoverageGap = CoverageGap.MISSING_SPANS
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    service_id: str
    coverage_level: CoverageLevel = CoverageLevel.NONE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/coverages")
async def record_coverage(
    body: RecordCoverageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_coverage(**body.model_dump())
    return result.model_dump()


@router.get("/coverages")
async def list_coverages(
    level: CoverageLevel | None = None,
    instrumentation: InstrumentationType | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_coverages(
            level=level,
            instrumentation=instrumentation,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/coverages/{record_id}")
async def get_coverage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_coverage(record_id)
    if result is None:
        raise HTTPException(404, f"Coverage record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_coverage_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_coverage_distribution()


@router.get("/low-coverage")
async def identify_low_coverage_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_coverage_services()


@router.get("/coverage-score-rankings")
async def rank_by_coverage_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage_score()


@router.get("/trends")
async def detect_coverage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_coverage_trends()


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


tca_route = router
