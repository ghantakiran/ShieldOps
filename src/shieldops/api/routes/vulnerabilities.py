"""Vulnerability management API endpoints."""

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user, require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/vulnerabilities", tags=["Vulnerabilities"])

# Module-level repository reference
_repository = None


def set_repository(repo: Any) -> None:
    global _repository
    _repository = repo


def _get_repo():
    if _repository is None:
        raise HTTPException(503, "Vulnerability service unavailable")
    return _repository


# Request/Response models
class VulnerabilityStatusUpdate(BaseModel):
    status: str = Field(
        description=(
            "New status: new, triaged, in_progress, remediated, verified, closed, accepted_risk"
        )
    )
    reason: str = ""


class VulnerabilityAssignment(BaseModel):
    team_id: str | None = None
    user_id: str | None = None


class CommentCreate(BaseModel):
    content: str
    comment_type: str = "comment"


class RiskAcceptanceCreate(BaseModel):
    reason: str
    expires_at: str | None = None  # ISO datetime string


VALID_STATUSES = {
    "new",
    "triaged",
    "in_progress",
    "remediated",
    "verified",
    "closed",
    "accepted_risk",
}

VALID_TRANSITIONS: dict[str, set[str]] = {
    "new": {"triaged", "in_progress", "accepted_risk"},
    "triaged": {"in_progress", "accepted_risk"},
    "in_progress": {"remediated", "accepted_risk"},
    "remediated": {"verified", "in_progress"},
    "verified": {"closed", "in_progress"},
    "closed": {"new"},  # reopen
    "accepted_risk": {"new", "triaged"},  # revoke acceptance
}


@router.get("")
async def list_vulnerabilities(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    scanner_type: str | None = Query(None),
    team_id: str | None = Query(None),
    sla_breached: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    vulns = await repo.list_vulnerabilities(
        status=status,
        severity=severity,
        scanner_type=scanner_type,
        team_id=team_id,
        sla_breached=sla_breached,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_vulnerabilities(
        status=status, severity=severity, sla_breached=sla_breached
    )
    return {"vulnerabilities": vulns, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
async def get_vulnerability_stats(
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    return await repo.get_vulnerability_stats()


@router.get("/sla-breaches")
async def list_sla_breaches(
    limit: int = Query(50, ge=1, le=200),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    vulns = await repo.list_vulnerabilities(sla_breached=True, limit=limit)
    return {"vulnerabilities": vulns, "total": len(vulns)}


@router.get("/{vuln_id}")
async def get_vulnerability(
    vuln_id: str,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    vuln = await repo.get_vulnerability(vuln_id)
    if vuln is None:
        raise HTTPException(404, f"Vulnerability {vuln_id} not found")
    comments = await repo.list_vulnerability_comments(vuln_id)
    vuln["comments"] = comments
    return vuln


@router.put("/{vuln_id}/status")
async def update_vulnerability_status(
    vuln_id: str,
    body: VulnerabilityStatusUpdate,
    _user=Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    repo = _get_repo()

    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status: {body.status}")

    vuln = await repo.get_vulnerability(vuln_id)
    if vuln is None:
        raise HTTPException(404, f"Vulnerability {vuln_id} not found")

    current = vuln["status"]
    allowed = VALID_TRANSITIONS.get(current, set())
    if body.status not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{current}' to '{body.status}'. Allowed: {sorted(allowed)}",
        )

    success = await repo.update_vulnerability_status(vuln_id, body.status)
    if not success:
        raise HTTPException(500, "Failed to update status")

    user_id = _user.id if hasattr(_user, "id") else _user.get("sub", "")

    # Log status change as comment
    await repo.add_vulnerability_comment(
        vulnerability_id=vuln_id,
        content=f"Status changed from '{current}' to '{body.status}'. {body.reason}".strip(),
        user_id=user_id,
        comment_type="status_change",
        metadata={"from_status": current, "to_status": body.status},
    )

    return {"id": vuln_id, "status": body.status, "previous_status": current}


@router.post("/{vuln_id}/assign")
async def assign_vulnerability(
    vuln_id: str,
    body: VulnerabilityAssignment,
    _user=Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    repo = _get_repo()

    vuln = await repo.get_vulnerability(vuln_id)
    if vuln is None:
        raise HTTPException(404, f"Vulnerability {vuln_id} not found")

    success = await repo.assign_vulnerability(
        vuln_id,
        team_id=body.team_id,
        user_id=body.user_id,
    )
    if not success:
        raise HTTPException(500, "Failed to assign vulnerability")

    user_id = _user.id if hasattr(_user, "id") else _user.get("sub", "")

    await repo.add_vulnerability_comment(
        vulnerability_id=vuln_id,
        content=f"Assigned to team={body.team_id}, user={body.user_id}",
        user_id=user_id,
        comment_type="assignment",
    )

    return {
        "id": vuln_id,
        "assigned_team_id": body.team_id,
        "assigned_user_id": body.user_id,
    }


@router.post("/{vuln_id}/comments")
async def add_comment(
    vuln_id: str,
    body: CommentCreate,
    _user=Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()

    vuln = await repo.get_vulnerability(vuln_id)
    if vuln is None:
        raise HTTPException(404, f"Vulnerability {vuln_id} not found")

    user_id = _user.id if hasattr(_user, "id") else _user.get("sub", "")

    comment_id = await repo.add_vulnerability_comment(
        vulnerability_id=vuln_id,
        content=body.content,
        user_id=user_id,
        comment_type=body.comment_type,
    )
    return {"id": comment_id, "vulnerability_id": vuln_id}


@router.get("/{vuln_id}/comments")
async def list_comments(
    vuln_id: str,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    repo = _get_repo()
    comments = await repo.list_vulnerability_comments(vuln_id)
    return {"comments": comments, "total": len(comments)}


@router.post("/{vuln_id}/accept-risk")
async def accept_risk(
    vuln_id: str,
    body: RiskAcceptanceCreate,
    _user=Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    repo = _get_repo()

    vuln = await repo.get_vulnerability(vuln_id)
    if vuln is None:
        raise HTTPException(404, f"Vulnerability {vuln_id} not found")

    expires: datetime | None = None
    if body.expires_at:
        try:
            expires = datetime.fromisoformat(body.expires_at)
        except ValueError as err:
            raise HTTPException(400, "Invalid expires_at format") from err

    user_id = _user.id if hasattr(_user, "id") else _user.get("sub", "unknown")

    acceptance_id = await repo.create_risk_acceptance(
        vulnerability_id=vuln_id,
        accepted_by=user_id,
        reason=body.reason,
        expires_at=expires,
    )

    return {"id": acceptance_id, "vulnerability_id": vuln_id, "status": "accepted_risk"}
