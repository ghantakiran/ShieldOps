"""Threat hunt orchestrator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.threat_hunt import (
    HuntStatus,
    HuntType,
    ThreatSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/threat-hunt",
    tags=["Threat Hunt"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Threat hunt service unavailable")
    return _engine


class RecordHuntRequest(BaseModel):
    campaign_name: str
    hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN
    hunt_status: HuntStatus = HuntStatus.PLANNING
    threat_severity: ThreatSeverity = ThreatSeverity.MEDIUM
    findings_count: int = 0
    details: str = ""


class AddFindingRequest(BaseModel):
    finding_label: str
    hunt_type: HuntType = HuntType.IOC_SWEEP
    threat_severity: ThreatSeverity = ThreatSeverity.HIGH
    confidence_score: float = 0.0


@router.post("/hunts")
async def record_hunt(
    body: RecordHuntRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_hunt(**body.model_dump())
    return result.model_dump()


@router.get("/hunts")
async def list_hunts(
    campaign_name: str | None = None,
    hunt_type: HuntType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_hunts(campaign_name=campaign_name, hunt_type=hunt_type, limit=limit)
    ]


@router.get("/hunts/{record_id}")
async def get_hunt(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_hunt(record_id)
    if result is None:
        raise HTTPException(404, f"Hunt '{record_id}' not found")
    return result.model_dump()


@router.post("/findings")
async def add_finding(
    body: AddFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_finding(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{campaign_name}")
async def analyze_hunt_effectiveness(
    campaign_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_hunt_effectiveness(campaign_name)


@router.get("/low-yield")
async def identify_low_yield_hunts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_yield_hunts()


@router.get("/rankings")
async def rank_by_findings_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_findings_count()


@router.get("/stagnation")
async def detect_hunt_stagnation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_hunt_stagnation()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


tho_route = router
