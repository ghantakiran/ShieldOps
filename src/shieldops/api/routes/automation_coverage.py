"""Automation Coverage Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.automation_coverage import (
    AutomationLevel,
    ProcessCategory,
)

logger = structlog.get_logger()
auc_route = APIRouter(
    prefix="/automation-coverage",
    tags=["Automation Coverage Analyzer"],
)

_instance: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _instance
    _instance = analyzer


def _get_analyzer() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Automation coverage service unavailable",
        )
    return _instance


class RegisterProcessRequest(BaseModel):
    process_name: str = ""
    category: ProcessCategory = ProcessCategory.DEPLOYMENT
    service_name: str = ""
    automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL
    manual_steps: int = 0
    automated_steps: int = 0
    gaps: list[str] = []


class CreateGoalRequest(BaseModel):
    category: ProcessCategory = ProcessCategory.DEPLOYMENT
    target_pct: float = 80.0
    deadline: str = ""


@auc_route.post("/register")
async def register_process(
    body: RegisterProcessRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    rec = ana.register_process(**body.model_dump())
    return rec.model_dump()  # type: ignore[no-any-return]


@auc_route.post("/goal")
async def create_goal(
    body: CreateGoalRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    goal = ana.create_goal(**body.model_dump())
    return goal.model_dump()  # type: ignore[no-any-return]


@auc_route.get("/stats")
async def get_stats(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    return ana.get_stats()  # type: ignore[no-any-return]


@auc_route.get("/report")
async def get_coverage_report(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    return ana.generate_coverage_report().model_dump()  # type: ignore[no-any-return]


@auc_route.get("/coverage")
async def get_coverage(
    category: ProcessCategory | None = None,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    return ana.calculate_coverage(category=category)  # type: ignore[no-any-return]


@auc_route.get("/gaps")
async def get_automation_gaps(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    ana = _get_analyzer()
    return ana.identify_automation_gaps()  # type: ignore[no-any-return]


@auc_route.get("/potential")
async def get_automation_potential(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    ana = _get_analyzer()
    return ana.rank_by_automation_potential()  # type: ignore[no-any-return]


@auc_route.get("/roi/{process_id}")
async def get_automation_roi(
    process_id: str,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    result = ana.estimate_automation_roi(process_id)
    if result is None:
        raise HTTPException(404, "Process not found")
    return result  # type: ignore[no-any-return]


@auc_route.get("")
async def list_processes(
    category: ProcessCategory | None = None,
    automation_level: AutomationLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    ana = _get_analyzer()
    return [  # type: ignore[no-any-return]
        p.model_dump()
        for p in ana.list_processes(
            category=category,
            automation_level=automation_level,
            limit=limit,
        )
    ]


@auc_route.get("/{process_id}")
async def get_process(
    process_id: str,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    ana = _get_analyzer()
    proc = ana.get_process(process_id)
    if proc is None:
        raise HTTPException(
            404,
            f"Process '{process_id}' not found",
        )
    return proc.model_dump()  # type: ignore[no-any-return]
