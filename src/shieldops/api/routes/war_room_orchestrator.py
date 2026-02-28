"""War room orchestrator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.war_room_orchestrator import (
    WarRoomPriority,
    WarRoomRole,
    WarRoomStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/war-room",
    tags=["War Room"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "War room service unavailable")
    return _engine


class RecordWarRoomRequest(BaseModel):
    incident_name: str
    role: WarRoomRole = WarRoomRole.INCIDENT_COMMANDER
    status: WarRoomStatus = WarRoomStatus.ASSEMBLING
    priority: WarRoomPriority = WarRoomPriority.SEV3
    participant_count: int = 0
    details: str = ""


class AddTemplateRequest(BaseModel):
    template_name: str
    role: WarRoomRole = WarRoomRole.INCIDENT_COMMANDER
    priority: WarRoomPriority = WarRoomPriority.SEV3
    auto_escalate: bool = True
    escalation_minutes: float = 30.0


@router.post("/war-rooms")
async def record_war_room(
    body: RecordWarRoomRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_war_room(**body.model_dump())
    return result.model_dump()


@router.get("/war-rooms")
async def list_war_rooms(
    incident_name: str | None = None,
    role: WarRoomRole | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_war_rooms(
            incident_name=incident_name,
            role=role,
            limit=limit,
        )
    ]


@router.get("/war-rooms/{record_id}")
async def get_war_room(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_war_room(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"War room '{record_id}' not found",
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
    return engine.analyze_war_room_effectiveness(incident_name)


@router.get("/stalled")
async def identify_stalled(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stalled_war_rooms()


@router.get("/rankings")
async def rank_by_participant_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_participant_count()


@router.get("/escalation-patterns")
async def detect_escalation_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_escalation_patterns()


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


wro_route = router
