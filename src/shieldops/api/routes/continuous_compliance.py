"""Continuous compliance validation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/continuous-compliance", tags=["Continuous Compliance"])

_validator: Any = None


def set_validator(validator: Any) -> None:
    global _validator
    _validator = validator


def _get_validator() -> Any:
    if _validator is None:
        raise HTTPException(503, "Continuous compliance service unavailable")
    return _validator


class RegisterControlRequest(BaseModel):
    framework: str
    control_id: str
    title: str
    description: str = ""
    severity: str = "medium"
    auto_remediate: bool = False


class ValidateControlRequest(BaseModel):
    control_id: str
    resource_id: str
    result: str
    evidence: str = ""
    remediation_action: str = ""


@router.post("/controls")
async def register_control(
    body: RegisterControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    control = validator.register_control(**body.model_dump())
    return control.model_dump()


@router.get("/controls")
async def list_controls(
    framework: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return [c.model_dump() for c in validator.list_controls(framework=framework)]


@router.delete("/controls/{control_id}")
async def delete_control(
    control_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    validator = _get_validator()
    if not validator.delete_control(control_id):
        raise HTTPException(404, f"Control '{control_id}' not found")
    return {"status": "deleted"}


@router.post("/validate")
async def validate_control(
    body: ValidateControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    record = validator.validate_control(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_records(
    control_id: str | None = None,
    result: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return [
        r.model_dump()
        for r in validator.list_records(control_id=control_id, result=result, limit=limit)
    ]


@router.get("/snapshot/{framework}")
async def get_snapshot(
    framework: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    return validator.get_snapshot(framework).model_dump()


@router.get("/failing")
async def get_failing_controls(
    framework: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return [r.model_dump() for r in validator.get_failing_controls(framework=framework)]


@router.get("/remediation-candidates")
async def get_remediation_candidates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return [c.model_dump() for c in validator.get_remediation_candidates()]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    return validator.get_stats()
