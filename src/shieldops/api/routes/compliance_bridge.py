"""Security compliance bridge API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.compliance_bridge import (
    BridgeStatus,
    MappingConfidence,
    SecurityFramework,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-bridge",
    tags=["Compliance Bridge"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance bridge service unavailable")
    return _engine


class RecordBridgeRequest(BaseModel):
    control_id: str
    control_name: str = ""
    framework: SecurityFramework = SecurityFramework.NIST
    bridge_status: BridgeStatus = BridgeStatus.NOT_ASSESSED
    alignment_score_pct: float = 0.0
    gap_description: str = ""


class AddMappingRequest(BaseModel):
    source_framework: SecurityFramework = SecurityFramework.NIST
    target_framework: SecurityFramework = SecurityFramework.CIS
    source_control_id: str = ""
    target_control_id: str = ""
    mapping_confidence: MappingConfidence = MappingConfidence.MODERATE
    notes: str = ""


@router.post("/bridges")
async def record_bridge(
    body: RecordBridgeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_bridge(**body.model_dump())
    return result.model_dump()


@router.get("/bridges")
async def list_bridges(
    framework: SecurityFramework | None = None,
    bridge_status: BridgeStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_bridges(framework=framework, bridge_status=bridge_status, limit=limit)
    ]


@router.get("/bridges/{record_id}")
async def get_bridge(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_bridge(record_id)
    if result is None:
        raise HTTPException(404, f"Bridge record '{record_id}' not found")
    return result.model_dump()


@router.post("/mappings")
async def add_mapping(
    body: AddMappingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_mapping(**body.model_dump())
    return result.model_dump()


@router.get("/alignment/{framework}")
async def analyze_alignment_by_framework(
    framework: SecurityFramework,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_alignment_by_framework(framework)


@router.get("/gaps")
async def identify_security_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_security_gaps()


@router.get("/rankings")
async def rank_by_alignment_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_alignment_score()


@router.get("/drift")
async def detect_alignment_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_alignment_drift()


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


scb_route = router
