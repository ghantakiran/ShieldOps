"""Escalation analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/escalation-analyzer", tags=["Escalation Analyzer"])

_analyzer: Any = None


def set_analyzer(inst: Any) -> None:
    global _analyzer
    _analyzer = inst


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Escalation analyzer service unavailable")
    return _analyzer


class RecordEscalationRequest(BaseModel):
    incident_id: str = ""
    from_tier: str = "L1"
    to_tier: str = "L2"
    reason: str = "manual"
    service: str = ""


class ResolveRequest(BaseModel):
    outcome: str


@router.post("/escalations")
async def record_escalation(
    body: RecordEscalationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    escalation = analyzer.record_escalation(**body.model_dump())
    return escalation.model_dump()


@router.get("/escalations")
async def list_escalations(
    service: str | None = None,
    reason: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        e.model_dump()
        for e in analyzer.list_escalations(service=service, reason=reason, limit=limit)
    ]


@router.get("/escalations/{escalation_id}")
async def get_escalation(
    escalation_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    escalation = analyzer.get_escalation(escalation_id)
    if escalation is None:
        raise HTTPException(404, f"Escalation '{escalation_id}' not found")
    return escalation.model_dump()


@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    body: ResolveRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    result = analyzer.resolve_escalation(escalation_id, outcome=body.outcome)
    if not result:
        raise HTTPException(404, f"Escalation '{escalation_id}' not found")
    return result.model_dump()


@router.get("/patterns")
async def detect_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [p.model_dump() for p in analyzer.detect_patterns()]


@router.get("/bottlenecks")
async def analyze_tier_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.analyze_tier_bottlenecks()


@router.get("/false-alarm-rate")
async def compute_false_alarm_rate(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, float]:
    analyzer = _get_analyzer()
    rate = analyzer.compute_false_alarm_rate(service=service)
    return {"false_alarm_rate": rate}


@router.get("/efficiency-report")
async def generate_efficiency_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_efficiency_report()


@router.get("/repeat-rate")
async def get_repeat_escalation_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, float]:
    analyzer = _get_analyzer()
    rate = analyzer.get_repeat_escalation_rate()
    return {"repeat_escalation_rate": rate}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
