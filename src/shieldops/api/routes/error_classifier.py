"""Error classifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.error_classifier import (
    ErrorCategory,
    ErrorSeverity,
    PatternType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/error-classifier",
    tags=["Error Classifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Error classifier service unavailable")
    return _engine


class RecordErrorRequest(BaseModel):
    service_name: str
    error_category: ErrorCategory = ErrorCategory.INTERNAL_ERROR
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    error_code: str = ""
    message: str = ""
    occurrence_count: int = 1


class AddPatternRequest(BaseModel):
    pattern_name: str
    pattern_type: PatternType = PatternType.ISOLATED
    error_category: ErrorCategory = ErrorCategory.INTERNAL_ERROR
    frequency_per_hour: float = 0.0
    affected_services: list[str] = []


@router.post("/errors")
async def record_error(
    body: RecordErrorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_error(**body.model_dump())
    return result.model_dump()


@router.get("/errors")
async def list_errors(
    service_name: str | None = None,
    error_category: ErrorCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_errors(
            service_name=service_name, error_category=error_category, limit=limit
        )
    ]


@router.get("/errors/{record_id}")
async def get_error(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_error(record_id)
    if result is None:
        raise HTTPException(404, f"Error record '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/distribution/{service_name}")
async def analyze_error_distribution(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_error_distribution(service_name)


@router.get("/recurring-patterns")
async def identify_recurring_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_recurring_patterns()


@router.get("/rankings")
async def rank_by_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_frequency()


@router.get("/trends")
async def detect_error_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_error_trends()


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


ecl_route = router
