"""Incident communication automator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.comm_automator import (
    CommAudience,
    CommChannel,
    CommType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/comm-automator",
    tags=["Comm Automator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Comm automator service unavailable",
        )
    return _engine


class RecordCommRequest(BaseModel):
    incident_name: str
    channel: CommChannel = CommChannel.SLACK
    comm_type: CommType = CommType.INITIAL_NOTIFICATION
    audience: CommAudience = CommAudience.ENGINEERING
    delivery_success: bool = True
    details: str = ""


class AddTemplateRequest(BaseModel):
    template_name: str
    channel: CommChannel = CommChannel.SLACK
    comm_type: CommType = CommType.INITIAL_NOTIFICATION
    audience: CommAudience = CommAudience.ENGINEERING
    auto_send: bool = False
    delay_minutes: float = 0.0


@router.post("/comms")
async def record_comm(
    body: RecordCommRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_comm(**body.model_dump())
    return result.model_dump()


@router.get("/comms")
async def list_comms(
    incident_name: str | None = None,
    channel: CommChannel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_comms(
            incident_name=incident_name,
            channel=channel,
            limit=limit,
        )
    ]


@router.get("/comms/{record_id}")
async def get_comm(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_comm(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Comm '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/templates")
async def add_template(
    body: AddTemplateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_template(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{incident_name}")
async def analyze_effectiveness(
    incident_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_comm_effectiveness(incident_name)


@router.get("/failed-deliveries")
async def identify_failed_deliveries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_deliveries()


@router.get("/rankings")
async def rank_by_comm_volume(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_comm_volume()


@router.get("/comm-gaps")
async def detect_comm_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_comm_gaps()


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


ica_route = router
