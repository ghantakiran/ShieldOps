"""Investigation API endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/investigations")
async def list_investigations(
    status: str | None = None,
    environment: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List active and recent investigations."""
    return {"investigations": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str) -> dict:
    """Get full investigation detail including reasoning chain and evidence."""
    return {"investigation_id": investigation_id, "status": "not_found"}


@router.post("/investigations/{investigation_id}/takeover")
async def takeover_investigation(investigation_id: str) -> dict:
    """Human takes over an active investigation from the agent."""
    return {"investigation_id": investigation_id, "action": "takeover"}
