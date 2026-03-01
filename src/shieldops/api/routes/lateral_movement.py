"""Lateral Movement Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.lateral_movement import (
    DetectionConfidence,
    MovementStage,
    MovementType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/lateral-movement", tags=["Lateral Movement"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Lateral movement service unavailable")
    return _engine


class RecordMovementRequest(BaseModel):
    incident_id: str
    movement_type: MovementType = MovementType.CREDENTIAL_HOPPING
    detection_confidence: DetectionConfidence = DetectionConfidence.LOW
    movement_stage: MovementStage = MovementStage.INITIAL_ACCESS
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddHopRequest(BaseModel):
    incident_id: str
    movement_type: MovementType = MovementType.CREDENTIAL_HOPPING
    source_host: str = ""
    destination_host: str = ""
    hop_count: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_movement(
    body: RecordMovementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_movement(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_movements(
    movement_type: MovementType | None = None,
    confidence: DetectionConfidence | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_movements(
            movement_type=movement_type,
            confidence=confidence,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_movement(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_movement(record_id)
    if result is None:
        raise HTTPException(404, f"Movement record '{record_id}' not found")
    return result.model_dump()


@router.post("/hops")
async def add_hop(
    body: AddHopRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_hop(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_movement_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_movement_patterns()


@router.get("/high-risk")
async def identify_high_risk_movements(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_movements()


@router.get("/risk-rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_movement_chains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_movement_chains()


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


lmd_route = router
