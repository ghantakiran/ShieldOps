"""Log Quality Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.log_quality import (
    LogIssueType,
    LogQualityDimension,
    LogQualityLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/log-quality", tags=["Log Quality"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Log quality service unavailable")
    return _engine


class RecordQualityRequest(BaseModel):
    service_id: str
    log_quality_dimension: LogQualityDimension = LogQualityDimension.STRUCTURE
    log_quality_level: LogQualityLevel = LogQualityLevel.ACCEPTABLE
    log_issue_type: LogIssueType = LogIssueType.UNSTRUCTURED
    quality_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddIssueRequest(BaseModel):
    issue_name: str
    log_quality_dimension: LogQualityDimension = LogQualityDimension.STRUCTURE
    quality_threshold: float = 0.0
    avg_quality_score: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_quality(
    body: RecordQualityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_quality(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_qualities(
    dimension: LogQualityDimension | None = None,
    level: LogQualityLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_qualities(
            dimension=dimension,
            level=level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_quality(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_quality(record_id)
    if result is None:
        raise HTTPException(404, f"Log quality record '{record_id}' not found")
    return result.model_dump()


@router.post("/issues")
async def add_issue(
    body: AddIssueRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_issue(**body.model_dump())
    return result.model_dump()


@router.get("/analysis")
async def analyze_log_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_log_quality()


@router.get("/poor-quality")
async def identify_poor_quality_logs(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_quality_logs()


@router.get("/quality-rankings")
async def rank_by_quality_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality_score()


@router.get("/regression")
async def detect_quality_regression(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_quality_regression()


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


lqa_route = router
