"""Performance Benchmark Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.perf_benchmark import (
    BenchmarkResult,
    BenchmarkType,
    ComparisonScope,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/perf-benchmark", tags=["Performance Benchmark"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Performance benchmark service unavailable")
    return _engine


class RecordBenchmarkRequest(BaseModel):
    service_name: str
    benchmark_type: BenchmarkType = BenchmarkType.LATENCY
    benchmark_result: BenchmarkResult = BenchmarkResult.BASELINE
    comparison_scope: ComparisonScope = ComparisonScope.SERVICE
    measured_value: float = 0.0
    baseline_value: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddBaselineRequest(BaseModel):
    service_pattern: str
    benchmark_type: BenchmarkType = BenchmarkType.LATENCY
    comparison_scope: ComparisonScope = ComparisonScope.SERVICE
    target_value: float = 0.0
    tolerance_pct: float = 10.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_benchmark(
    body: RecordBenchmarkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_benchmark(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_benchmarks(
    benchmark_type: BenchmarkType | None = None,
    benchmark_result: BenchmarkResult | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_benchmarks(
            benchmark_type=benchmark_type,
            benchmark_result=benchmark_result,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_benchmark(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_benchmark(record_id)
    if result is None:
        raise HTTPException(404, f"Benchmark record '{record_id}' not found")
    return result.model_dump()


@router.post("/baselines")
async def add_baseline(
    body: AddBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_benchmark_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_benchmark_distribution()


@router.get("/regressions")
async def identify_regressions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_regressions()


@router.get("/deviation-rankings")
async def rank_by_deviation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_deviation()


@router.get("/trends")
async def detect_benchmark_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_benchmark_trends()


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


pbt_route = router
