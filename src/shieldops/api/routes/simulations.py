"""API routes for remediation simulation (dry-run)."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter()

_simulator: Any | None = None


def set_simulator(simulator: Any) -> None:
    global _simulator
    _simulator = simulator


class SimulateRequest(BaseModel):
    action_type: str
    target_resource: str
    environment: str = "production"
    risk_level: str = "low"
    parameters: dict[str, Any] = Field(default_factory=dict)


@router.post("/remediations/simulate")
async def simulate_remediation(
    request: SimulateRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Simulate a remediation action without executing it."""
    if not _simulator:
        raise HTTPException(status_code=503, detail="Simulator not initialized")

    result = await _simulator.simulate(
        action_type=request.action_type,
        target_resource=request.target_resource,
        environment=request.environment,
        risk_level=request.risk_level,
        parameters=request.parameters,
    )
    return {"simulation": result.model_dump(mode="json")}


@router.get("/remediations/simulations")
async def list_simulations(
    limit: int = Query(50, ge=1, le=200),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List recent simulations."""
    if not _simulator:
        return {"simulations": [], "total": 0}
    sims = _simulator.list_simulations(limit=limit)
    return {
        "simulations": [s.model_dump(mode="json") for s in sims],
        "total": len(sims),
    }


@router.get("/remediations/simulations/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific simulation result."""
    if not _simulator:
        raise HTTPException(status_code=503, detail="Simulator not initialized")
    result = _simulator.get_simulation(simulation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {"simulation": result.model_dump(mode="json")}
