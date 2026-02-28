"""Incident response timer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.response_timer import (
    BenchmarkType,
    ResponsePhase,
    ResponseSpeed,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/response-timer",
    tags=["Response Timer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Response timer service unavailable")
    return _engine


class RecordResponseTimeRequest(BaseModel):
    service_name: str
    phase: ResponsePhase = ResponsePhase.DETECTION
    speed: ResponseSpeed = ResponseSpeed.EXCELLENT
    benchmark_type: BenchmarkType = BenchmarkType.INDUSTRY
    duration_minutes: float = 0.0
    details: str = ""


class AddBenchmarkRequest(BaseModel):
    benchmark_name: str
    phase: ResponsePhase = ResponsePhase.DETECTION
    speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE
    target_minutes: float = 30.0
    percentile: float = 95.0


@router.post("/responses")
async def record_response_time(
    body: RecordResponseTimeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_response_time(**body.model_dump())
    return result.model_dump()


@router.get("/responses")
async def list_response_times(
    service_name: str | None = None,
    phase: ResponsePhase | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_response_times(service_name=service_name, phase=phase, limit=limit)
    ]


@router.get("/responses/{record_id}")
async def get_response_time(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_response_time(record_id)
    if result is None:
        raise HTTPException(404, f"Response time '{record_id}' not found")
    return result.model_dump()


@router.post("/benchmarks")
async def add_benchmark(
    body: AddBenchmarkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_benchmark(**body.model_dump())
    return result.model_dump()


@router.get("/speed/{service_name}")
async def analyze_response_speed(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_response_speed(service_name)


@router.get("/slow-responses")
async def identify_slow_responses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_responses()


@router.get("/rankings")
async def rank_by_response_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_response_time()


@router.get("/response-trends")
async def detect_response_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_response_trends()


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


irt_route = router
