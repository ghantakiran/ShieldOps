"""Incident severity validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.severity_validator import (
    SeverityCriteria,
    SeverityLevel,
    ValidationOutcome,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/severity-validator",
    tags=["Severity Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Incident severity validator service unavailable",
        )
    return _engine


class RecordValidationRequest(BaseModel):
    incident_id: str
    assigned_severity: SeverityLevel = SeverityLevel.SEV3
    validated_severity: SeverityLevel = SeverityLevel.SEV3
    outcome: ValidationOutcome = ValidationOutcome.CORRECT
    criteria: SeverityCriteria = SeverityCriteria.SERVICE_DEGRADATION
    accuracy_score: float = 100.0
    validator_id: str = ""
    details: str = ""


class AddCriterionRequest(BaseModel):
    criteria: SeverityCriteria = SeverityCriteria.SERVICE_DEGRADATION
    severity_level: SeverityLevel = SeverityLevel.SEV3
    threshold_description: str = ""
    weight: float = 1.0
    active: bool = True


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
    incident_id: str | None = None,
    outcome: ValidationOutcome | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_validations(
            incident_id=incident_id,
            outcome=outcome,
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


@router.post("/criteria")
async def add_criterion(
    body: AddCriterionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_criterion(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy/{validator_id}")
async def analyze_validation_accuracy(
    validator_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_validation_accuracy(validator_id)


@router.get("/misclassified")
async def identify_misclassified_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_misclassified_incidents()


@router.get("/rankings")
async def rank_by_accuracy_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_accuracy_score()


@router.get("/bias")
async def detect_classification_bias(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_classification_bias()


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


svl_route = router
