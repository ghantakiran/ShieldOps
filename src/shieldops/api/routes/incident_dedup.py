"""Incident deduplication API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-dedup",
    tags=["Incident Dedup"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident dedup service unavailable")
    return _engine


class SubmitIncidentRequest(BaseModel):
    title: str
    description: str = ""
    source: str = "manual"
    service: str = ""
    severity: str = ""


class ManualMergeRequest(BaseModel):
    primary_id: str
    merge_ids: list[str]


@router.post("/incidents")
async def submit_incident(
    body: SubmitIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    incident = engine.submit_incident(
        title=body.title,
        description=body.description,
        source=body.source,
        service=body.service,
        severity=body.severity,
    )
    return incident.model_dump()


@router.get("/incidents/{incident_id}/duplicates")
async def find_duplicates(
    incident_id: str,
    strategy: str = "fingerprint",
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    candidates = engine.find_duplicates(incident_id, strategy=strategy)
    return [c.model_dump() for c in candidates]


@router.post("/incidents/{incident_id}/auto-merge")
async def auto_merge(
    incident_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    merged = engine.auto_merge(incident_id)
    if merged is None:
        raise HTTPException(404, "No candidates found for auto-merge")
    return merged.model_dump()


@router.post("/merge")
async def manual_merge(
    body: ManualMergeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    merged = engine.manual_merge(primary_id=body.primary_id, merge_ids=body.merge_ids)
    if merged is None:
        raise HTTPException(404, "Invalid incident IDs for merge")
    return merged.model_dump()


@router.put("/candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    candidate = engine.reject_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, f"Candidate '{candidate_id}' not found")
    return candidate.model_dump()


@router.get("/candidates")
async def list_candidates(
    incident_id: str | None = None,
    decision: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    candidates = engine.list_candidates(incident_id=incident_id, decision=decision)
    return [c.model_dump() for c in candidates[-limit:]]


@router.get("/merged")
async def list_merged(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [m.model_dump() for m in engine.list_merged()]


@router.get("/merged/{merged_id}")
async def get_merged(
    merged_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    merged = engine.get_merged(merged_id)
    if merged is None:
        raise HTTPException(404, f"Merged incident '{merged_id}' not found")
    return merged.model_dump()


@router.get("/fingerprint")
async def compute_fingerprint(
    title: str,
    service: str = "",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    fp = engine.compute_fingerprint(title, service)
    return {"title": title, "service": service, "fingerprint": fp}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
