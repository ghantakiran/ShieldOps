"""Config validation engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.config.config_validator import (
    ConfigScope,
    ValidationResult,
    ValidationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/config-validator",
    tags=["Config Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Config validator service unavailable")
    return _engine


class RecordValidationRequest(BaseModel):
    config_name: str
    validation_type: ValidationType = ValidationType.SCHEMA
    result: ValidationResult = ValidationResult.PASSED
    scope: ConfigScope = ConfigScope.APPLICATION
    failure_rate_pct: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    validation_type: ValidationType = ValidationType.SCHEMA
    result: ValidationResult = ValidationResult.PASSED
    scope: ConfigScope = ConfigScope.APPLICATION
    max_allowed_failures: int = 3


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
    config_name: str | None = None,
    validation_type: ValidationType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_validations(
            config_name=config_name, validation_type=validation_type, limit=limit
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
        raise HTTPException(404, f"Validation '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/health/{config_name}")
async def analyze_validation_health(
    config_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_validation_health(config_name)


@router.get("/failing")
async def identify_failing_configs(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_configs()


@router.get("/rankings")
async def rank_by_failure_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_failure_rate()


@router.get("/trends")
async def detect_validation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


cvn_route = router
