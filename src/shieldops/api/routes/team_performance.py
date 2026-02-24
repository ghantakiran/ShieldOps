"""Team performance analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/team-performance",
    tags=["Team Performance"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Team performance service unavailable")
    return _analyzer


class RegisterMemberRequest(BaseModel):
    name: str
    team: str = ""
    role: str = ""
    skills: list[str] | None = None


class RecordActivityRequest(BaseModel):
    member_id: str
    activity_type: str = "incident"
    duration_minutes: float = 0.0
    oncall_hours: float = 0.0
    incident_resolved: bool = False


@router.post("/members")
async def register_member(
    body: RegisterMemberRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    member = analyzer.register_member(
        name=body.name,
        team=body.team,
        role=body.role,
        skills=body.skills,
    )
    return member.model_dump()


@router.get("/members")
async def list_members(
    team: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    members = analyzer.list_members(team=team, limit=limit)
    return [m.model_dump() for m in members]


@router.get("/members/{member_id}")
async def get_member(
    member_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    member = analyzer.get_member(member_id)
    if member is None:
        raise HTTPException(404, f"Member '{member_id}' not found")
    return member.model_dump()


@router.post("/activities")
async def record_activity(
    body: RecordActivityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.record_activity(
        member_id=body.member_id,
        activity_type=body.activity_type,
        duration_minutes=body.duration_minutes,
        oncall_hours=body.oncall_hours,
        incident_resolved=body.incident_resolved,
    )


@router.post("/performance/{team}")
async def compute_performance(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.compute_performance(team).model_dump()


@router.get("/silos")
async def detect_knowledge_silos(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    silos = analyzer.detect_knowledge_silos(team=team)
    return [s.model_dump() for s in silos]


@router.get("/burnout")
async def assess_burnout_risk(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    risks = analyzer.assess_burnout_risk(team=team)
    return [r.model_dump() for r in risks]


@router.get("/health/{team}")
async def get_team_health(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_team_health(team)


@router.get("/recommendations/{team}")
async def get_recommendations(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_recommendations(team)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
