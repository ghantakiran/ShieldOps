"""Agent fleet management API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.models.base import AgentStatus

if TYPE_CHECKING:
    from shieldops.agents.registry import AgentRegistry

router = APIRouter()

_registry: AgentRegistry | None = None


def set_registry(registry: AgentRegistry | None) -> None:
    global _registry
    _registry = registry


@router.get("/agents")
async def list_agents(
    environment: str | None = None,
    status: AgentStatus | None = None,
    _user: UserResponse = Depends(get_current_user),
) -> dict:
    """List all deployed agents with status and health."""
    if _registry:
        items = await _registry.list_agents(
            environment=environment,
            status=status.value if status else None,
        )
        return {
            "agents": items,
            "total": len(items),
            "filters": {"environment": environment, "status": status},
        }
    return {
        "agents": [],
        "total": 0,
        "filters": {"environment": environment, "status": status},
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, _user: UserResponse = Depends(get_current_user)) -> dict:
    """Get detailed agent information including config and recent activity."""
    if _registry:
        result = await _registry.get_agent(agent_id)
        if result:
            return result
    raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/agents/{agent_id}/enable")
async def enable_agent(
    agent_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict:
    """Enable a disabled agent."""
    if _registry:
        result = await _registry.enable(agent_id)
        if result:
            return {"agent_id": agent_id, "action": "enabled", "agent": result}
    raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/agents/{agent_id}/disable")
async def disable_agent(
    agent_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict:
    """Disable an active agent (graceful shutdown)."""
    if _registry:
        result = await _registry.disable(agent_id)
        if result:
            return {"agent_id": agent_id, "action": "disabled", "agent": result}
    raise HTTPException(status_code=404, detail="Agent not found")
