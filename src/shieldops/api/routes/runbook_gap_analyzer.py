"""Runbook gap analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
rga_route = APIRouter(
    prefix="/runbook-gap-analyzer",
    tags=["Runbook Gap Analyzer"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Runbook gap analyzer service unavailable",
        )
    return _instance


# -- Request models --


class RegisterGapRequest(BaseModel):
    service_name: str
    scenario: str = ""
    severity: str = "low"
    category: str = "no_runbook"
    source: str = "automated_scan"
    incident_count: int = 0


class CreateRemediationRequest(BaseModel):
    gap_id: str
    action: str = ""
    assignee: str = ""


# -- Routes --


@rga_route.post("/gaps")
async def register_gap(
    body: RegisterGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    gap = engine.register_gap(**body.model_dump())
    return gap.model_dump()


@rga_route.get("/gaps")
async def list_gaps(
    service_name: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        g.model_dump()
        for g in engine.list_gaps(
            service_name=service_name,
            severity=severity,
            category=category,
            limit=limit,
        )
    ]


@rga_route.get("/gaps/{gap_id}")
async def get_gap(
    gap_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    gap = engine.get_gap(gap_id)
    if gap is None:
        raise HTTPException(404, f"Gap '{gap_id}' not found")
    return gap.model_dump()


@rga_route.post("/remediations")
async def create_remediation(
    body: CreateRemediationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    remediation = engine.create_remediation(**body.model_dump())
    if remediation is None:
        raise HTTPException(404, f"Gap '{body.gap_id}' not found")
    return remediation.model_dump()


@rga_route.get("/remediations")
async def list_remediations(
    gap_id: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_remediations(
            gap_id=gap_id,
            limit=limit,
        )
    ]


@rga_route.post("/resolve/{gap_id}")
async def resolve_gap(
    gap_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.mark_gap_resolved(gap_id)
    if not result:
        raise HTTPException(404, f"Gap '{gap_id}' not found")
    return {"resolved": True, "gap_id": gap_id}


@rga_route.get("/incident-correlation")
async def get_incident_correlation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.correlate_incidents_to_gaps()


@rga_route.get("/prioritized")
async def get_prioritized(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [g.model_dump() for g in engine.prioritize_gaps()]


@rga_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_gap_report().model_dump()


@rga_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
