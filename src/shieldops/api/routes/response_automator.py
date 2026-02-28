"""Security response automator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.response_automator import (
    ResponseAction,
    ResponseOutcome,
    ResponseUrgency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/response-automator",
    tags=["Response Automator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Response automator service unavailable")
    return _engine


class RecordResponseRequest(BaseModel):
    incident_id: str
    response_action: ResponseAction = ResponseAction.ISOLATE_HOST
    response_outcome: ResponseOutcome = ResponseOutcome.SUCCESS
    response_urgency: ResponseUrgency = ResponseUrgency.STANDARD
    execution_time_seconds: float = 0.0
    details: str = ""


class AddPlaybookRequest(BaseModel):
    playbook_name: str
    response_action: ResponseAction = ResponseAction.BLOCK_IP
    response_urgency: ResponseUrgency = ResponseUrgency.HIGH
    step_count: int = 0


@router.post("/responses")
async def record_response(
    body: RecordResponseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_response(**body.model_dump())
    return result.model_dump()


@router.get("/responses")
async def list_responses(
    incident_id: str | None = None,
    response_action: ResponseAction | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_responses(
            incident_id=incident_id, response_action=response_action, limit=limit
        )
    ]


@router.get("/responses/{record_id}")
async def get_response(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_response(record_id)
    if result is None:
        raise HTTPException(404, f"Response '{record_id}' not found")
    return result.model_dump()


@router.post("/playbooks")
async def add_playbook(
    body: AddPlaybookRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_playbook(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{incident_id}")
async def analyze_response_effectiveness(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_response_effectiveness(incident_id)


@router.get("/failed-responses")
async def identify_failed_responses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_responses()


@router.get("/rankings")
async def rank_by_execution_speed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_execution_speed()


@router.get("/response-loops")
async def detect_response_loops(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_response_loops()


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


sra_route = router
