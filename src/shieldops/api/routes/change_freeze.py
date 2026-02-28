"""Change freeze manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_freeze import (
    ExceptionStatus,
    FreezeScope,
    FreezeType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-freeze",
    tags=["Change Freeze"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change freeze service unavailable")
    return _engine


class RecordFreezeRequest(BaseModel):
    freeze_name: str
    freeze_type: FreezeType = FreezeType.FULL
    scope: FreezeScope = FreezeScope.GLOBAL
    exception_status: ExceptionStatus = ExceptionStatus.PENDING
    duration_hours: float = 0.0
    details: str = ""


class AddExceptionRequest(BaseModel):
    exception_name: str
    freeze_type: FreezeType = FreezeType.FULL
    scope: FreezeScope = FreezeScope.GLOBAL
    reason: str = ""
    approved_by: str = ""


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
    freeze_name: str | None = None,
    freeze_type: FreezeType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_freezes(freeze_name=freeze_name, freeze_type=freeze_type, limit=limit)
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


@router.post("/exceptions")
async def add_exception(
    body: AddExceptionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_exception(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{freeze_name}")
async def analyze_freeze_effectiveness(
    freeze_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_freeze_effectiveness(freeze_name)


@router.get("/frequent-exceptions")
async def identify_frequent_exceptions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequent_exceptions()


@router.get("/rankings")
async def rank_by_freeze_duration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_freeze_duration()


@router.get("/freeze-patterns")
async def detect_freeze_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_freeze_patterns()


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


cfm_route = router
