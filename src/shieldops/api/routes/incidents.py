"""API routes for correlated incidents."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()
router = APIRouter()

# Module-level singleton
_engine = None
_repository = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def set_repository(repo: Any) -> None:
    global _repository
    _repository = repo


class MergeRequest(BaseModel):
    source_id: str
    target_id: str


class UpdateStatusRequest(BaseModel):
    status: str  # open, investigating, resolved


@router.get("/incidents")
async def list_incidents(
    status: str | None = Query(None),
    service: str | None = Query(None),
    environment: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if not _engine:
        return {"incidents": [], "total": 0}
    incidents = _engine.list_incidents(
        status=status,
        service=service,
        environment=environment,
        limit=limit,
        offset=offset,
    )
    return {
        "incidents": [i.model_dump(mode="json") for i in incidents],
        "total": len(incidents),
    }


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if not _engine:
        raise HTTPException(status_code=404, detail="Correlation engine not initialized")
    incident = _engine.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Enrich with investigation details
    investigations = []
    if _repository:
        for inv_id in incident.investigation_ids:
            inv = await _repository.get_investigation(inv_id)
            if inv:
                investigations.append(inv)

    result: dict[str, Any] = incident.model_dump(mode="json")
    result["investigations"] = investigations
    return result


@router.post("/incidents/merge")
async def merge_incidents(
    request: MergeRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    if not _engine:
        raise HTTPException(status_code=503, detail="Correlation engine not initialized")
    result = _engine.merge(request.source_id, request.target_id)
    if not result:
        raise HTTPException(
            status_code=400, detail="Merge failed — invalid incident IDs or same incident"
        )
    return {"merged_incident": result.model_dump(mode="json")}


@router.put("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: UpdateStatusRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    if not _engine:
        raise HTTPException(status_code=503, detail="Correlation engine not initialized")
    valid_statuses = {"open", "investigating", "resolved"}
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    success = _engine.update_status(incident_id, request.status)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident = _engine.get_incident(incident_id)
    return {"incident": incident.model_dump(mode="json") if incident else {}}


@router.get("/incidents/for-investigation/{investigation_id}")
async def get_incident_for_investigation(
    investigation_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if not _engine:
        return {"incident": None}
    incident = _engine.get_incident_for_investigation(investigation_id)
    if not incident:
        return {"incident": None}
    return {"incident": incident.model_dump(mode="json")}
