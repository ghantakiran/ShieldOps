"""Alert grouping engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/alert-grouping", tags=["Alert Grouping"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert grouping service unavailable")
    return _engine


class IngestAlertRequest(BaseModel):
    alert_name: str
    service: str = ""
    labels: dict[str, str] = Field(default_factory=dict)


class CreateRuleRequest(BaseModel):
    name: str
    strategy: str = "fingerprint"
    match_labels: dict[str, str] = Field(default_factory=dict)
    service_pattern: str = ""
    window_seconds: int = 300
    priority: int = 0


class MergeGroupsRequest(BaseModel):
    group_ids: list[str]


@router.post("/alerts")
async def ingest_alert(
    body: IngestAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.ingest_alert(**body.model_dump())


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
    removed = engine.delete_rule(rule_id)
    if not removed:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"deleted": True, "rule_id": rule_id}


@router.get("/groups")
async def list_groups(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [g.model_dump() for g in engine.list_groups(status=status)]


@router.get("/groups/{group_id}")
async def get_group(
    group_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    group = engine.get_group(group_id)
    if group is None:
        raise HTTPException(404, f"Group '{group_id}' not found")
    return group.model_dump()


@router.post("/groups/merge")
async def merge_groups(
    body: MergeGroupsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    merged = engine.merge_groups(body.group_ids)
    if merged is None:
        raise HTTPException(404, "One or more groups not found")
    return merged.model_dump()


@router.put("/groups/{group_id}/resolve")
async def resolve_group(
    group_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    group = engine.resolve_group(group_id)
    if group is None:
        raise HTTPException(404, f"Group '{group_id}' not found")
    return group.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
