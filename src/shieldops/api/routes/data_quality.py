"""Data quality monitoring API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/data-quality", tags=["Data Quality"])

_monitor: Any = None


def set_monitor(monitor: Any) -> None:
    global _monitor
    _monitor = monitor


def _get_monitor() -> Any:
    if _monitor is None:
        raise HTTPException(503, "Data quality service unavailable")
    return _monitor


class CreateRuleRequest(BaseModel):
    name: str
    dataset: str
    dimension: str
    expression: str = ""
    threshold: float = 0.95
    owner: str = ""


class RunCheckRequest(BaseModel):
    rule_id: str
    score: float
    records_checked: int = 0
    records_failed: int = 0
    details: str = ""


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    rule = monitor.create_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/rules")
async def list_rules(
    dataset: str | None = None,
    dimension: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [r.model_dump() for r in monitor.list_rules(dataset=dataset, dimension=dimension)]


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    rule = monitor.get_rule(rule_id)
    if rule is None:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return rule.model_dump()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    removed = monitor.delete_rule(rule_id)
    if not removed:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"deleted": True, "rule_id": rule_id}


@router.post("/checks")
async def run_check(
    body: RunCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.run_check(**body.model_dump())
    return result.model_dump()


@router.get("/checks")
async def get_check_history(
    rule_id: str | None = None,
    dataset: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [
        r.model_dump()
        for r in monitor.get_check_history(rule_id=rule_id, dataset=dataset, limit=limit)
    ]


@router.get("/alerts")
async def list_alerts(
    dataset: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [a.model_dump() for a in monitor.list_alerts(dataset=dataset, limit=limit)]


@router.get("/datasets/{dataset}/health")
async def get_dataset_health(
    dataset: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_dataset_health(dataset)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_stats()
