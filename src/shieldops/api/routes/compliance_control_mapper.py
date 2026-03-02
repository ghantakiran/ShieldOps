"""Compliance Control Mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.compliance_control_mapper import (
    ComplianceFramework,
    ControlStatus,
    MappingConfidence,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-control-mapper",
    tags=["Compliance Control Mapper"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance control mapper service unavailable")
    return _engine


class RecordMappingRequest(BaseModel):
    control_name: str
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    control_status: ControlStatus = ControlStatus.IMPLEMENTED
    mapping_confidence: MappingConfidence = MappingConfidence.EXACT_MATCH
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    control_name: str
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    analysis_score: float = 0.0
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
    compliance_framework: ComplianceFramework | None = None,
    control_status: ControlStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_mappings(
            compliance_framework=compliance_framework,
            control_status=control_status,
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
        raise HTTPException(404, f"Mapping record '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_mapping_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_mapping_distribution()


@router.get("/coverage-gaps")
async def identify_coverage_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_coverage_gaps()


@router.get("/coverage-rankings")
async def rank_by_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage()


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


ccm_route = router
