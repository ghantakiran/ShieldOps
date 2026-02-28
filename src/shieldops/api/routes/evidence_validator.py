"""Compliance evidence validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.evidence_validator import (
    EvidenceFramework,
    EvidenceType,
    ValidationStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/evidence-validator",
    tags=["Evidence Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance evidence validator service unavailable")
    return _engine


class RecordValidationRequest(BaseModel):
    evidence_id: str
    control_id: str
    evidence_type: EvidenceType = EvidenceType.AUTOMATED_SCAN
    status: ValidationStatus | None = None
    framework: EvidenceFramework = EvidenceFramework.SOC2
    validity_score: float = 0.0
    reviewer: str = ""
    details: str = ""


class AddFindingRequest(BaseModel):
    evidence_id: str
    control_id: str
    framework: EvidenceFramework = EvidenceFramework.SOC2
    finding_type: str = ""
    severity: str = "low"
    description: str = ""


@router.post("/validations")
async def record_validation(
    body: RecordValidationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_validation(**body.model_dump())
    return result.model_dump()


@router.get("/validations")
async def list_validations(
    framework: EvidenceFramework | None = None,
    status: ValidationStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_validations(
            framework=framework,
            status=status,
            limit=limit,
        )
    ]


@router.get("/validations/{record_id}")
async def get_validation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_validation(record_id)
    if result is None:
        raise HTTPException(404, f"Validation record '{record_id}' not found")
    return result.model_dump()


@router.post("/findings")
async def add_finding(
    body: AddFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_finding(**body.model_dump())
    return result.model_dump()


@router.get("/framework/{framework}")
async def analyze_validation_by_framework(
    framework: EvidenceFramework,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_validation_by_framework(framework)


@router.get("/invalid")
async def identify_invalid_evidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_invalid_evidence()


@router.get("/rankings")
async def rank_by_validity_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_validity_score()


@router.get("/gaps")
async def detect_validation_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_validation_gaps()


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


evl_route = router
