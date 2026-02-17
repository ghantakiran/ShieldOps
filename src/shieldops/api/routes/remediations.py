"""Remediation API endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/remediations")
async def list_remediations(
    environment: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List remediation timeline (newest first)."""
    return {"remediations": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/remediations/{remediation_id}")
async def get_remediation(remediation_id: str) -> dict:
    """Get remediation detail with before/after diff and audit trail."""
    return {"remediation_id": remediation_id, "status": "not_found"}


@router.post("/remediations/{remediation_id}/approve")
async def approve_remediation(remediation_id: str) -> dict:
    """Approve a pending remediation action."""
    return {"remediation_id": remediation_id, "action": "approved"}


@router.post("/remediations/{remediation_id}/deny")
async def deny_remediation(remediation_id: str) -> dict:
    """Deny a pending remediation action."""
    return {"remediation_id": remediation_id, "action": "denied"}


@router.post("/remediations/{remediation_id}/rollback")
async def rollback_remediation(remediation_id: str) -> dict:
    """Rollback a completed remediation to pre-action state."""
    return {"remediation_id": remediation_id, "action": "rollback_initiated"}
