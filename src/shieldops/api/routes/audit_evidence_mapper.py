"""Audit Evidence Mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.audit_evidence_mapper import (
    ControlFramework,
    EvidenceType,
    MappingStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-evidence-mapper",
    tags=["Audit Evidence Mapper"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit evidence mapper service unavailable")
    return _engine


class RecordMappingRequest(BaseModel):
    control_id: str
    control_framework: ControlFramework = ControlFramework.SOC2
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    evidence_type: EvidenceType = EvidenceType.MANUAL
    mapping_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddGapRequest(BaseModel):
    control_id: str
    control_framework: ControlFramework = ControlFramework.SOC2
    gap_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/mappings")
async def record_mapping(
    body: RecordMappingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_mapping(**body.model_dump())
    return result.model_dump()


@router.get("/mappings")
async def list_mappings(
    framework: ControlFramework | None = None,
    status: MappingStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_mappings(
            framework=framework,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/mappings/{record_id}")
async def get_mapping(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_mapping(record_id)
    if result is None:
        raise HTTPException(404, f"Mapping '{record_id}' not found")
    return result.model_dump()


@router.post("/gaps")
async def add_gap(
    body: AddGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_gap(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def analyze_mapping_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_mapping_coverage()


@router.get("/unmapped")
async def identify_unmapped_controls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unmapped_controls()


@router.get("/mapping-score-rankings")
async def rank_by_mapping_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_mapping_score()


@router.get("/trends")
async def detect_mapping_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_mapping_trends()


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


aem_route = router
