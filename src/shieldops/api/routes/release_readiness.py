"""Release readiness checker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.release_readiness import (
    CheckPriority,
    ReadinessCategory,
    ReadinessStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/release-readiness",
    tags=["Release Readiness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Release readiness service unavailable")
    return _engine


class RecordReadinessRequest(BaseModel):
    release_name: str
    category: ReadinessCategory = ReadinessCategory.TEST_COVERAGE
    status: ReadinessStatus = ReadinessStatus.READY
    priority: CheckPriority = CheckPriority.CRITICAL
    score_pct: float = 0.0
    details: str = ""


class AddCheckRequest(BaseModel):
    check_name: str
    category: ReadinessCategory = ReadinessCategory.TEST_COVERAGE
    status: ReadinessStatus = ReadinessStatus.READY
    min_required_score_pct: float = 0.0
    is_blocking: bool = True


@router.post("/readiness")
async def record_readiness(
    body: RecordReadinessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_readiness(**body.model_dump())
    return result.model_dump()


@router.get("/readiness")
async def list_readiness_checks(
    release_name: str | None = None,
    category: ReadinessCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_readiness_checks(
            release_name=release_name, category=category, limit=limit
        )
    ]


@router.get("/readiness/{record_id}")
async def get_readiness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_readiness(record_id)
    if result is None:
        raise HTTPException(404, f"Readiness '{record_id}' not found")
    return result.model_dump()


@router.post("/checks")
async def add_check(
    body: AddCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_check(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{release_name}")
async def analyze_release_readiness(
    release_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_release_readiness(release_name)


@router.get("/blockers")
async def identify_blockers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_blockers()


@router.get("/rankings")
async def rank_by_readiness_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_readiness_score()


@router.get("/trends")
async def detect_readiness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_readiness_trends()


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


rrc_route = router
