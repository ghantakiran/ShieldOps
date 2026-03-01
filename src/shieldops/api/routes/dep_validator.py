"""Service Dependency Validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dep_validator import (
    DependencyDirection,
    ValidationResult,
    ValidationSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dep-validator",
    tags=["Dependency Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Dependency validator service unavailable",
        )
    return _engine


class RecordValidationRequest(BaseModel):
    service: str
    dependency: str = ""
    result: ValidationResult = ValidationResult.VALID
    direction: DependencyDirection = DependencyDirection.UNKNOWN
    severity: ValidationSeverity = ValidationSeverity.INFO
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    service_pattern: str
    result: ValidationResult = ValidationResult.VALID
    direction: DependencyDirection = DependencyDirection.UNKNOWN
    threshold_pct: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


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
    result: ValidationResult | None = None,
    direction: DependencyDirection | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_validations(
            result=result,
            direction=direction,
            team=team,
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
        raise HTTPException(
            404,
            f"Validation '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/results")
async def analyze_validation_results(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_validation_results()


@router.get("/undeclared")
async def identify_undeclared_deps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_undeclared_deps()


@router.get("/invalid-rankings")
async def rank_by_invalid_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_invalid_count()


@router.get("/trends")
async def detect_validation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_validation_trends()


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


dvl_route = router
