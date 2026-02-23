"""Compliance automation rule engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-automation",
    tags=["Compliance Automation"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance automation service unavailable")
    return _engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateRuleRequest(BaseModel):
    name: str
    description: str = ""
    framework: str = ""
    condition: str = ""
    action: str = "notify"
    severity: str = "medium"
    tags: list[str] = Field(default_factory=list)


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    action: str | None = None
    status: str | None = None
    severity: str | None = None


class ReportViolationRequest(BaseModel):
    resource_id: str
    resource_type: str = ""
    description: str = ""
    severity: str = "medium"
    rule_id: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.create_rule(
        name=body.name,
        description=body.description,
        framework=body.framework,
        condition=body.condition,
        action=body.action,
        severity=body.severity,
        tags=body.tags,
    )
    return rule.model_dump()


@router.get("/rules")
async def list_rules(
    status: str | None = None,
    action: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    rules = engine.list_rules(status=status, action=action)
    return [r.model_dump() for r in rules[-limit:]]


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: UpdateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    rule = engine.update_rule(rule_id, **updates)
    if rule is None:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return rule.model_dump()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    deleted = engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"deleted": True, "rule_id": rule_id}


@router.post("/violations")
async def report_violation(
    body: ReportViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    violation = engine.report_violation(
        resource_id=body.resource_id,
        resource_type=body.resource_type,
        description=body.description,
        severity=body.severity,
        rule_id=body.rule_id,
    )
    return violation.model_dump()


@router.post("/violations/{violation_id}/evaluate")
async def evaluate_violation(
    violation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    executions = engine.evaluate_violation(violation_id)
    return [e.model_dump() for e in executions]


@router.get("/violations")
async def list_violations(
    resource_type: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    violations = engine.list_violations(
        resource_type=resource_type,
        severity=severity,
        limit=limit,
    )
    return [v.model_dump() for v in violations]


@router.get("/executions")
async def list_executions(
    rule_id: str | None = None,
    result: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    executions = engine.list_executions(rule_id=rule_id, result=result, limit=limit)
    return [e.model_dump() for e in executions]


@router.get("/effectiveness")
async def get_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_effectiveness()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
