"""Security Posture Benchmarker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.posture_benchmark import (
    BenchmarkCategory,
    BenchmarkGrade,
    BenchmarkSource,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/posture-benchmark",
    tags=["Posture Benchmark"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Security posture benchmarker service unavailable",
        )
    return _engine


class RecordBenchmarkRequest(BaseModel):
    service: str
    category: BenchmarkCategory = BenchmarkCategory.INFRASTRUCTURE
    grade: BenchmarkGrade = BenchmarkGrade.AVERAGE
    source: BenchmarkSource = BenchmarkSource.INDUSTRY_STANDARD
    benchmark_score: float = 0.0
    peer_score: float = 0.0
    passing: bool = False
    details: str = ""


class AddComparisonRequest(BaseModel):
    comparison_name: str
    category: BenchmarkCategory = BenchmarkCategory.INFRASTRUCTURE
    source: BenchmarkSource = BenchmarkSource.INDUSTRY_STANDARD
    our_score: float = 0.0
    benchmark_score: float = 0.0
    delta: float = 0.0
    service: str = ""
    description: str = ""


@router.post("/records")
async def record_benchmark(
    body: RecordBenchmarkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_benchmark(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_benchmarks(
    category: BenchmarkCategory | None = None,
    grade: BenchmarkGrade | None = None,
    source: BenchmarkSource | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_benchmarks(
            category=category,
            grade=grade,
            source=source,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_benchmark(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_benchmark(record_id)
    if record is None:
        raise HTTPException(404, f"Benchmark record '{record_id}' not found")
    return record.model_dump()


@router.post("/comparisons")
async def add_comparison(
    body: AddComparisonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    comparison = engine.add_comparison(**body.model_dump())
    return comparison.model_dump()


@router.get("/by-category")
async def analyze_benchmark_by_category(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_benchmark_by_category()


@router.get("/lagging")
async def identify_lagging_areas(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_lagging_areas()


@router.get("/rank-by-score")
async def rank_by_benchmark_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_benchmark_score()


@router.get("/trends")
async def detect_benchmark_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_benchmark_trends()


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


spb_route = router
