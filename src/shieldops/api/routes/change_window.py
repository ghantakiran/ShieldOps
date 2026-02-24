"""Change window optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_window import (
    DayOfWeek,
    WindowType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-window",
    tags=["Change Window"],
)

_instance: Any = None


def set_optimizer(optimizer: Any) -> None:
    global _instance
    _instance = optimizer


def _get_optimizer() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Change window service unavailable",
        )
    return _instance


# -- Request models --


class RecordChangeRequest(BaseModel):
    service_name: str = ""
    window_type: WindowType = WindowType.STANDARD
    day_of_week: DayOfWeek = DayOfWeek.TUESDAY
    hour: int = 10
    is_success: bool = True
    risk_level: str = "low"
    duration_minutes: int = 30


class WindowScoreRequest(BaseModel):
    day_of_week: DayOfWeek
    hour: int


# -- Routes --


@router.post("/records")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    record = optimizer.record_change(
        **body.model_dump(),
    )
    return record.model_dump()


@router.get("/records")
async def list_records(
    service_name: str | None = None,
    window_type: WindowType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        r.model_dump()
        for r in optimizer.list_records(
            service_name=service_name,
            window_type=window_type,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    record = optimizer.get_record(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/score")
async def calculate_score(
    body: WindowScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    score = optimizer.calculate_window_score(
        body.day_of_week,
        body.hour,
    )
    return score.model_dump()


@router.get("/optimal")
async def find_optimal(
    service_name: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        s.model_dump()
        for s in optimizer.find_optimal_windows(
            service_name=service_name,
        )
    ]


@router.get("/risky")
async def get_risky_windows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [s.model_dump() for s in optimizer.detect_risky_windows()]


@router.get("/by-day")
async def analyze_by_day(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.analyze_by_day_of_week()


@router.get("/by-type")
async def compare_types(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.compare_window_types()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.generate_window_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.get_stats()
