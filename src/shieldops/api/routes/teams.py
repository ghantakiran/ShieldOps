"""Team management API endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/teams", tags=["Teams"])

_repository = None


def set_repository(repo: Any) -> None:
    global _repository
    _repository = repo


def _get_repo():
    if _repository is None:
        raise HTTPException(503, "Team service unavailable")
    return _repository


class TeamCreate(BaseModel):
    name: str
    description: str = ""
    slack_channel: str = ""
    pagerduty_service_id: str = ""
    email: str = ""


class TeamMemberAdd(BaseModel):
    user_id: str
    role: str = "member"


@router.post("")
async def create_team(
    body: TeamCreate,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    repo = _get_repo()
    team = await repo.create_team(
        name=body.name,
        description=body.description,
        slack_channel=body.slack_channel,
        pagerduty_service_id=body.pagerduty_service_id,
        email=body.email,
    )
    return team


@router.get("")
async def list_teams(
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    teams = await repo.list_teams()
    return {"teams": teams, "total": len(teams)}


@router.get("/{team_id}")
async def get_team(
    team_id: str,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    team = await repo.get_team(team_id)
    if team is None:
        raise HTTPException(404, f"Team {team_id} not found")
    members = await repo.list_team_members(team_id)
    team["members"] = members

    # Get vulnerability counts for this team
    vulns = await repo.list_vulnerabilities(team_id=team_id, limit=0)
    team["vulnerability_count"] = len(vulns)
    return team


@router.post("/{team_id}/members")
async def add_member(
    team_id: str,
    body: TeamMemberAdd,
    _user: Any = Depends(require_role("admin", "operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    repo = _get_repo()
    team = await repo.get_team(team_id)
    if team is None:
        raise HTTPException(404, f"Team {team_id} not found")

    member_id = await repo.add_team_member(
        team_id=team_id,
        user_id=body.user_id,
        role=body.role,
    )
    return {
        "id": member_id,
        "team_id": team_id,
        "user_id": body.user_id,
        "role": body.role,
    }


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(
    team_id: str,
    user_id: str,
    _user: Any = Depends(require_role("admin", "operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    repo = _get_repo()
    success = await repo.remove_team_member(team_id, user_id)
    if not success:
        raise HTTPException(404, "Member not found in team")
    return {"removed": True, "team_id": team_id, "user_id": user_id}
