"""Security Compliance Mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.compliance_mapper import (
    ComplianceFramework,
    ComplianceRisk,
    ControlStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-mapper",
    tags=["Compliance Mapper"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Compliance mapper service unavailable",
        )
    return _engine


class RecordMappingRequest(BaseModel):
    model_config = {"extra": "forbid"}

    framework: ComplianceFramework = ComplianceFramework.SOC2
    control_id: str = ""
    control_name: str = ""
    status: ControlStatus = ControlStatus.UNDER_REVIEW
    risk: ComplianceRisk = ComplianceRisk.MODERATE
    compliance_score: float = 0.0
    owner: str = ""
    details: str = ""


class AddEvidenceRequest(BaseModel):
    model_config = {"extra": "forbid"}

    control_id: str
    evidence_type: str
    evidence_description: str
    collected_at: float


@router.post("/records")
async def record_mapping(
    body: RecordMappingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_mapping(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_mappings(
    framework: ComplianceFramework | None = None,
    status: ControlStatus | None = None,
    risk: ComplianceRisk | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_mappings(
            framework=framework,
            status=status,
            risk=risk,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_mapping(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_mapping(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Mapping '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/evidence")
async def add_evidence(
    body: AddEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    evidence = engine.add_evidence(**body.model_dump())
    return evidence.model_dump()


@router.get("/by-framework")
async def analyze_compliance_by_framework(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_by_framework()


@router.get("/non-compliant")
async def identify_non_compliant_controls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_non_compliant_controls()


@router.get("/rank-by-score")
async def rank_by_compliance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance_score()


@router.get("/trends")
async def detect_compliance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_compliance_trends()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
    return report.model_dump()


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


scm2_route = router
