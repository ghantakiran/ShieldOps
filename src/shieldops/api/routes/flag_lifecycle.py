"""Feature flag lifecycle manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.config.flag_lifecycle import (
    CleanupReason,
    FlagLifecycleStage,
    FlagRisk,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/flag-lifecycle",
    tags=["Flag Lifecycle"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Flag lifecycle service unavailable")
    return _engine


class RecordFlagRequest(BaseModel):
    flag_name: str
    owner: str = ""
    risk: FlagRisk = FlagRisk.LOW
    age_days: int = 0
    references_count: int = 0
    details: str = ""


class RecordCleanupCandidateRequest(BaseModel):
    flag_name: str
    reason: CleanupReason = CleanupReason.FULLY_ROLLED_OUT
    risk: FlagRisk = FlagRisk.LOW
    tech_debt_score: float = 0.0
    details: str = ""


@router.post("/flags")
async def record_flag(
    body: RecordFlagRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_flag(**body.model_dump())
    return result.model_dump()


@router.get("/flags")
async def list_flags(
    flag_name: str | None = None,
    stage: FlagLifecycleStage | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_flags(flag_name=flag_name, stage=stage, limit=limit)
    ]


@router.get("/flags/{record_id}")
async def get_flag(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_flag(record_id)
    if result is None:
        raise HTTPException(404, f"Flag '{record_id}' not found")
    return result.model_dump()


@router.post("/cleanup-candidates")
async def record_cleanup_candidate(
    body: RecordCleanupCandidateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_cleanup_candidate(**body.model_dump())
    return result.model_dump()


@router.get("/stale")
async def identify_stale_flags(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_flags()


@router.get("/cleanup-candidates")
async def identify_cleanup_candidates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_cleanup_candidates()


@router.get("/tech-debt")
async def calculate_tech_debt_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_tech_debt_score()


@router.get("/owner-responsibility")
async def analyze_owner_responsibility(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_owner_responsibility()


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


fl_route = router
