"""Cost attribution and chargeback API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-attribution", tags=["Cost Attribution"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost attribution service unavailable")
    return _engine


class CreateRuleRequest(BaseModel):
    name: str
    team: str
    method: str = "tag_based"
    match_tags: dict[str, str] = Field(default_factory=dict)
    match_services: list[str] = Field(default_factory=list)
    proportion: float = 1.0


class RecordCostRequest(BaseModel):
    service: str
    amount: float
    resource_id: str = ""
    currency: str = "USD"
    tags: dict[str, str] = Field(default_factory=dict)
    period: str = ""


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.create_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/rules")
async def list_rules(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_rules(team=team)]


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    if not engine.delete_rule(rule_id):
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"status": "deleted"}


@router.post("/costs")
async def record_cost(
    body: RecordCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    entry = engine.record_cost(**body.model_dump())
    return entry.model_dump()


@router.get("/costs")
async def list_entries(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [e.model_dump() for e in engine.list_entries(service=service, limit=limit)]


@router.post("/allocate")
async def allocate_costs(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.allocate_costs()]


@router.get("/report/{team}")
async def get_team_report(
    team: str,
    period: str = "",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_team_report(team, period=period).model_dump()


@router.get("/unattributed")
async def get_unattributed_costs(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [e.model_dump() for e in engine.get_unattributed_costs()]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
