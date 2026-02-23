"""Infrastructure cost budget manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/budget-manager",
    tags=["Budget Manager"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Budget manager service unavailable")
    return _manager


class CreateBudgetRequest(BaseModel):
    name: str
    limit_amount: float
    period: str = "monthly"
    owner: str = ""
    team: str = ""


class RecordSpendRequest(BaseModel):
    amount: float
    category: str = "other"
    description: str = ""


class AdjustLimitRequest(BaseModel):
    new_limit: float


@router.post("/budgets")
async def create_budget(
    body: CreateBudgetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    budget = mgr.create_budget(
        name=body.name,
        limit_amount=body.limit_amount,
        period=body.period,
        owner=body.owner,
        team=body.team,
    )
    return budget.model_dump()


@router.get("/budgets")
async def list_budgets(
    team: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    budgets = mgr.list_budgets(team=team, status=status)
    return [b.model_dump() for b in budgets[-limit:]]


@router.get("/budgets/{budget_id}")
async def get_budget(
    budget_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    budget = mgr.get_budget(budget_id)
    if budget is None:
        raise HTTPException(404, f"Budget '{budget_id}' not found")
    return budget.model_dump()


@router.put("/budgets/{budget_id}/limit")
async def adjust_limit(
    budget_id: str,
    body: AdjustLimitRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    budget = mgr.adjust_limit(budget_id, body.new_limit)
    if budget is None:
        raise HTTPException(404, f"Budget '{budget_id}' not found")
    return budget.model_dump()


@router.post("/budgets/{budget_id}/spend")
async def record_spend(
    budget_id: str,
    body: RecordSpendRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    entry = mgr.record_spend(
        budget_id,
        amount=body.amount,
        category=body.category,
        description=body.description,
    )
    if entry is None:
        raise HTTPException(404, f"Budget '{budget_id}' not found")
    return entry.model_dump()


@router.get("/budgets/{budget_id}/burn-rate")
async def compute_burn_rate(
    budget_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    report = mgr.compute_burn_rate(budget_id)
    if report is None:
        raise HTTPException(404, f"Budget '{budget_id}' not found")
    return report.model_dump()


@router.get("/budgets/{budget_id}/entries")
async def list_entries(
    budget_id: str,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    entries = mgr.list_spend_entries(budget_id, category=category, limit=limit)
    return [e.model_dump() for e in entries]


@router.get("/budgets/{budget_id}/status")
async def check_status(
    budget_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    status = mgr.check_budget_status(budget_id)
    if status is None:
        raise HTTPException(404, f"Budget '{budget_id}' not found")
    return {"budget_id": budget_id, "status": status}


@router.get("/alerts")
async def get_alerts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    alerts = mgr.get_over_budget_alerts()
    return [b.model_dump() for b in alerts]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
