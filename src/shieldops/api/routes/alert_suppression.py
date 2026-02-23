"""Alert suppression and maintenance window API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/alert-suppression", tags=["Alert Suppression"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert suppression service unavailable")
    return _engine


class AddRuleRequest(BaseModel):
    name: str
    match_labels: dict[str, str] = Field(default_factory=dict)
    match_pattern: str = ""
    description: str = ""
    expires_at: float | None = None
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduleWindowRequest(BaseModel):
    name: str
    start_time: float
    end_time: float
    services: list[str] = Field(default_factory=list)
    description: str = ""
    created_by: str = ""
    suppress_labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CheckRequest(BaseModel):
    alert_name: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    service: str = ""


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.add_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/rules")
async def list_rules(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_rules()]


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    removed = engine.remove_rule(rule_id)
    if not removed:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"deleted": True, "rule_id": rule_id}


@router.post("/windows")
async def schedule_window(
    body: ScheduleWindowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    window = engine.schedule_window(**body.model_dump())
    return window.model_dump()


@router.get("/windows")
async def list_windows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [w.model_dump() for w in engine.get_active_windows()]


@router.post("/check")
async def check_suppression(
    body: CheckRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.should_suppress(**body.model_dump())
    return result.model_dump()
