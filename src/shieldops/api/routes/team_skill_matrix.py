"""Team skill matrix API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/team-skill-matrix",
    tags=["Team Skill Matrix"],
)

_matrix: Any = None


def set_matrix(matrix: Any) -> None:
    global _matrix
    _matrix = matrix


def _get_matrix() -> Any:
    if _matrix is None:
        raise HTTPException(
            503,
            "Team skill matrix service unavailable",
        )
    return _matrix


# -- Request models -------------------------------------------------


class RegisterSkillRequest(BaseModel):
    member_name: str
    team: str = ""
    skill_name: str = ""
    domain: str = "INFRASTRUCTURE"
    level: str = "NOVICE"
    certifications: list[str] = []


class AssessSkillRequest(BaseModel):
    new_level: str


# -- Routes ---------------------------------------------------------


@router.post("/skills")
async def register_skill(
    body: RegisterSkillRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    matrix = _get_matrix()
    entry = matrix.register_skill(**body.model_dump())
    return entry.model_dump()


@router.get("/skills")
async def list_skills(
    member_name: str | None = None,
    team: str | None = None,
    domain: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    matrix = _get_matrix()
    return [
        e.model_dump()
        for e in matrix.list_skills(
            member_name=member_name,
            team=team,
            domain=domain,
            limit=limit,
        )
    ]


@router.get("/skills/{entry_id}")
async def get_skill(
    entry_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    matrix = _get_matrix()
    entry = matrix.get_skill(entry_id)
    if entry is None:
        raise HTTPException(
            404,
            f"Skill entry '{entry_id}' not found",
        )
    return entry.model_dump()


@router.post("/skills/{entry_id}/assess")
async def assess_skill(
    entry_id: str,
    body: AssessSkillRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    matrix = _get_matrix()
    entry = matrix.assess_skill(entry_id, body.new_level)
    if entry is None:
        raise HTTPException(
            404,
            f"Skill entry '{entry_id}' not found",
        )
    return entry.model_dump()


@router.get("/gaps")
async def identify_skill_gaps(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    matrix = _get_matrix()
    return [g.model_dump() for g in matrix.identify_skill_gaps(team=team)]


@router.get("/coverage/{team}")
async def calculate_team_coverage(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    matrix = _get_matrix()
    return matrix.calculate_team_coverage(team)


@router.get("/spofs")
async def find_single_points_of_failure(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    matrix = _get_matrix()
    return matrix.find_single_points_of_failure(team=team)


@router.get("/training")
async def recommend_training(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    matrix = _get_matrix()
    return matrix.recommend_training(team=team)


@router.get("/report")
async def generate_skill_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    matrix = _get_matrix()
    return matrix.generate_skill_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    matrix = _get_matrix()
    return matrix.get_stats()
