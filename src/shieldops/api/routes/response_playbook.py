"""Incident Response Playbook Manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.response_playbook import (
    PlaybookEffectiveness,
    PlaybookStatus,
    PlaybookType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/response-playbook", tags=["Response Playbook"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Response playbook service unavailable")
    return _engine


class RecordPlaybookRequest(BaseModel):
    playbook_name: str
    playbook_type: PlaybookType = PlaybookType.MANUAL
    playbook_status: PlaybookStatus = PlaybookStatus.DRAFT
    playbook_effectiveness: PlaybookEffectiveness = PlaybookEffectiveness.UNTESTED
    coverage_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddUsageRequest(BaseModel):
    usage_name: str
    playbook_type: PlaybookType = PlaybookType.MANUAL
    execution_count: int = 0
    avg_resolution_time: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_playbook(
    body: RecordPlaybookRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_playbook(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_playbooks(
    playbook_type: PlaybookType | None = None,
    status: PlaybookStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_playbooks(
            playbook_type=playbook_type,
            status=status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_playbook(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_playbook(record_id)
    if result is None:
        raise HTTPException(404, f"Playbook record '{record_id}' not found")
    return result.model_dump()


@router.post("/usages")
async def add_usage(
    body: AddUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_usage(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def analyze_playbook_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_playbook_coverage()


@router.get("/gaps")
async def identify_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_gaps()


@router.get("/effectiveness-rankings")
async def rank_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_effectiveness()


@router.get("/trends")
async def detect_playbook_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_playbook_trends()


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


irp_route = router
