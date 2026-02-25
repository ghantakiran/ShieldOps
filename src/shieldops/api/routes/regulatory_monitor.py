"""Regulatory Change Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.regulatory_monitor import (
    ChangeUrgency,
    ComplianceImpact,
    RegulatoryBody,
)

logger = structlog.get_logger()
rgm_route = APIRouter(
    prefix="/regulatory-monitor",
    tags=["Regulatory Change Monitor"],
)

_instance: Any = None


def set_monitor(monitor: Any) -> None:
    global _instance
    _instance = monitor


def _get_monitor() -> Any:
    if _instance is None:
        raise HTTPException(503, "Regulatory monitor service unavailable")
    return _instance


class RecordChangeRequest(BaseModel):
    body: RegulatoryBody = RegulatoryBody.NIST
    regulation: str = ""
    change_summary: str = ""
    urgency: ChangeUrgency = ChangeUrgency.INFORMATIONAL
    impact: ComplianceImpact = ComplianceImpact.NO_IMPACT
    affected_controls: list[str] = []
    effective_date: str = ""


class AssessImpactRequest(BaseModel):
    change_id: str
    service_name: str = ""
    effort_hours: float = 0.0
    assessor: str = ""


class MarkAddressedRequest(BaseModel):
    change_id: str


@rgm_route.post("/record")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    change = mon.record_change(**body.model_dump())
    return change.model_dump()  # type: ignore[no-any-return]


@rgm_route.post("/assess")
async def assess_impact(
    body: AssessImpactRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    result = mon.assess_impact(**body.model_dump())
    if result is None:
        raise HTTPException(404, "Change not found")
    return result.model_dump()  # type: ignore[no-any-return]


@rgm_route.post("/addressed")
async def mark_addressed(
    body: MarkAddressedRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    result = mon.mark_addressed(body.change_id)
    if result is None:
        raise HTTPException(404, "Change not found")
    return result.model_dump()  # type: ignore[no-any-return]


@rgm_route.get("/stats")
async def get_stats(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    return mon.get_stats()  # type: ignore[no-any-return]


@rgm_route.get("/report")
async def get_regulatory_report(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    return mon.generate_regulatory_report().model_dump()  # type: ignore[no-any-return]


@rgm_route.get("/overdue")
async def get_overdue_changes(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    mon = _get_monitor()
    return [  # type: ignore[no-any-return]
        c.model_dump() for c in mon.identify_overdue_changes()
    ]


@rgm_route.get("/compliance-gap")
async def get_compliance_gap(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    return mon.calculate_compliance_gap()  # type: ignore[no-any-return]


@rgm_route.get("/effort")
async def get_total_effort(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    return mon.estimate_total_effort()  # type: ignore[no-any-return]


@rgm_route.get("")
async def list_changes(
    body: RegulatoryBody | None = None,
    urgency: ChangeUrgency | None = None,
    limit: int = 50,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    mon = _get_monitor()
    return [  # type: ignore[no-any-return]
        c.model_dump()
        for c in mon.list_changes(
            body=body,
            urgency=urgency,
            limit=limit,
        )
    ]


@rgm_route.get("/{change_id}")
async def get_change(
    change_id: str,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    mon = _get_monitor()
    change = mon.get_change(change_id)
    if change is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return change.model_dump()  # type: ignore[no-any-return]
