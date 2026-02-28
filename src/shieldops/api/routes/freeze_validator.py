"""Change freeze validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.freeze_validator import (
    FreezeStatus,
    FreezeType,
    FreezeViolation,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/freeze-validator",
    tags=["Freeze Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Freeze validator service unavailable",
        )
    return _engine


class RecordFreezeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    freeze_name: str
    freeze_type: FreezeType = FreezeType.FULL_FREEZE
    status: FreezeStatus = FreezeStatus.ACTIVE
    team: str = ""
    environment: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    details: str = ""


class AddViolationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    freeze_id: str
    violation_type: FreezeViolation = FreezeViolation.UNAUTHORIZED_DEPLOY
    deployer: str = ""
    service: str = ""
    severity_score: float = 0.0


@router.post("/freezes")
async def record_freeze(
    body: RecordFreezeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_freeze(**body.model_dump())
    return result.model_dump()


@router.get("/freezes")
async def list_freezes(
    freeze_type: FreezeType | None = None,
    status: FreezeStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_freezes(
            freeze_type=freeze_type,
            status=status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/freezes/{record_id}")
async def get_freeze(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_freeze(record_id)
    if result is None:
        raise HTTPException(404, f"Freeze '{record_id}' not found")
    return result.model_dump()


@router.post("/violations")
async def add_violation(
    body: AddViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_violation(**body.model_dump())
    return result.model_dump()


@router.get("/compliance")
async def analyze_freeze_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_freeze_compliance()


@router.get("/frequent-violators")
async def identify_frequent_violators(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequent_violators()


@router.get("/rankings")
async def rank_by_severity_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_severity_score()


@router.get("/trends")
async def detect_violation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_violation_trends()


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


cfv_route = router
