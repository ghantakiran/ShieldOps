"""Cross-Team Dependency Risk API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.cross_team_risk import (
    CoordinationNeed,
    DependencyDirection,
    RiskLevel,
)

logger = structlog.get_logger()
ctr_route = APIRouter(
    prefix="/cross-team-risk",
    tags=["Cross-Team Dependency Risk"],
)

_instance: Any = None


def set_risk_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Cross-team risk service unavailable",
        )
    return _instance


class RegisterDepRequest(BaseModel):
    source_team: str = ""
    target_team: str = ""
    source_service: str = ""
    target_service: str = ""
    direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    risk_level: RiskLevel = RiskLevel.LOW
    coordination_need: CoordinationNeed = CoordinationNeed.NOTIFICATION
    sla_impact_pct: float = 0.0


class AssessChangeRequest(BaseModel):
    dep_id: str
    change_description: str = ""
    assessed_by: str = ""


@ctr_route.post("/register")
async def register_dependency(
    body: RegisterDepRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    eng = _get_engine()
    dep = eng.register_dependency(**body.model_dump())
    return dep.model_dump()  # type: ignore[no-any-return]


@ctr_route.post("/assess")
async def assess_change_risk(
    body: AssessChangeRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    eng = _get_engine()
    result = eng.assess_change_risk(**body.model_dump())
    if result is None:
        raise HTTPException(404, "Dependency not found")
    return result.model_dump()  # type: ignore[no-any-return]


@ctr_route.get("/stats")
async def get_stats(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    eng = _get_engine()
    return eng.get_stats()  # type: ignore[no-any-return]


@ctr_route.get("/report")
async def get_risk_report(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    eng = _get_engine()
    return eng.generate_risk_report().model_dump()  # type: ignore[no-any-return]


@ctr_route.get("/critical-paths")
async def get_critical_paths(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return eng.identify_critical_paths()  # type: ignore[no-any-return]


@ctr_route.get("/circular")
async def get_circular_deps(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return eng.detect_circular_dependencies()  # type: ignore[no-any-return]


@ctr_route.get("/team-ranking")
async def get_team_ranking(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return eng.rank_teams_by_risk()  # type: ignore[no-any-return]


@ctr_route.get("/blast-radius/{team}")
async def get_blast_radius(
    team: str,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    eng = _get_engine()
    return eng.calculate_blast_radius(team)  # type: ignore[no-any-return]


@ctr_route.get("")
async def list_dependencies(
    source_team: str | None = None,
    target_team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return [  # type: ignore[no-any-return]
        d.model_dump()
        for d in eng.list_dependencies(
            source_team=source_team,
            target_team=target_team,
            limit=limit,
        )
    ]


@ctr_route.get("/{dep_id}")
async def get_dependency(
    dep_id: str,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    eng = _get_engine()
    dep = eng.get_dependency(dep_id)
    if dep is None:
        raise HTTPException(
            404,
            f"Dependency '{dep_id}' not found",
        )
    return dep.model_dump()  # type: ignore[no-any-return]
