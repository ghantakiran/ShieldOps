"""Agent fleet management API endpoints."""

from fastapi import APIRouter

from shieldops.models.base import AgentStatus

router = APIRouter()


@router.get("/agents")
async def list_agents(
    environment: str | None = None,
    status: AgentStatus | None = None,
) -> dict:
    """List all deployed agents with status and health."""
    # TODO: Query agent registry from database
    return {
        "agents": [],
        "total": 0,
        "filters": {"environment": environment, "status": status},
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    """Get detailed agent information including config and recent activity."""
    # TODO: Query agent detail from database
    return {"agent_id": agent_id, "status": "not_found"}


@router.post("/agents/{agent_id}/enable")
async def enable_agent(agent_id: str) -> dict:
    """Enable a disabled agent."""
    return {"agent_id": agent_id, "action": "enabled"}


@router.post("/agents/{agent_id}/disable")
async def disable_agent(agent_id: str) -> dict:
    """Disable an active agent (graceful shutdown)."""
    return {"agent_id": agent_id, "action": "disabled"}
