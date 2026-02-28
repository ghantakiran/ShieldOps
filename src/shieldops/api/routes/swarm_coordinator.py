"""Agent swarm coordinator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.swarm_coordinator import (
    ConflictResolution,
    SwarmRole,
    SwarmStatus,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/swarm-coordinator",
    tags=["Swarm Coordinator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Swarm Coordinator service unavailable")
    return _engine


class RecordSwarmRequest(BaseModel):
    incident_id: str
    swarm_role: SwarmRole = SwarmRole.LEADER
    swarm_status: SwarmStatus = SwarmStatus.FORMING
    conflict_resolution: ConflictResolution = ConflictResolution.LEADER_DECIDES
    agent_count: int = 0
    details: str = ""


class AddAssignmentRequest(BaseModel):
    agent_name: str
    swarm_role: SwarmRole = SwarmRole.INVESTIGATOR
    swarm_status: SwarmStatus = SwarmStatus.ACTIVE
    utilization_pct: float = 0.0


@router.post("/swarms")
async def record_swarm(
    body: RecordSwarmRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_swarm(**body.model_dump())
    return result.model_dump()


@router.get("/swarms")
async def list_swarms(
    incident_id: str | None = None,
    swarm_status: SwarmStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_swarms(incident_id=incident_id, swarm_status=swarm_status, limit=limit)
    ]


@router.get("/swarms/{record_id}")
async def get_swarm(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_swarm(record_id)
    if result is None:
        raise HTTPException(404, f"Swarm '{record_id}' not found")
    return result.model_dump()


@router.post("/assignments")
async def add_assignment(
    body: AddAssignmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assignment(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{incident_id}")
async def analyze_swarm_effectiveness(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_swarm_effectiveness(incident_id)


@router.get("/idle-agents")
async def identify_idle_agents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_idle_agents()


@router.get("/rankings")
async def rank_by_completion_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_completion_rate()


@router.get("/coordination-conflicts")
async def detect_coordination_conflicts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_coordination_conflicts()


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


swc_route = router
