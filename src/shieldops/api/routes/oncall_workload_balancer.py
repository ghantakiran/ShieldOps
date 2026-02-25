"""On-call workload balancer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
owb_route = APIRouter(
    prefix="/oncall-workload-balancer",
    tags=["On-Call Workload Balancer"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "On-call workload balancer service unavailable",
        )
    return _instance


# -- Request models --


class RecordWorkloadRequest(BaseModel):
    team_member: str
    team_name: str = ""
    period_label: str = ""
    page_count: int = 0
    after_hours_pages: int = 0
    incident_duration_minutes: float = 0.0
    weekend_shifts: int = 0
    escalation_count: int = 0


class ComparePeriodRequest(BaseModel):
    period_labels: list[str]


# -- Routes --


@owb_route.post("/workloads")
async def record_workload(
    body: RecordWorkloadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_workload(**body.model_dump())
    return record.model_dump()


@owb_route.get("/workloads")
async def list_workloads(
    team_name: str | None = None,
    team_member: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        w.model_dump()
        for w in engine.list_workloads(
            team_name=team_name,
            team_member=team_member,
            limit=limit,
        )
    ]


@owb_route.get("/workloads/{record_id}")
async def get_workload(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_workload(record_id)
    if record is None:
        raise HTTPException(404, f"Workload record '{record_id}' not found")
    return record.model_dump()


@owb_route.get("/balance/{team_name}")
async def compute_balance(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compute_balance_score(team_name)


@owb_route.post("/suggest/{team_name}")
async def suggest_rebalance(
    team_name: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    suggestion = engine.suggest_rebalance(team_name)
    return suggestion.model_dump()


@owb_route.get("/suggestions")
async def list_suggestions(
    team_name: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_suggestions(
            team_name=team_name,
            limit=limit,
        )
    ]


@owb_route.get("/overloaded")
async def get_overloaded(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overloaded_members()


@owb_route.post("/compare-periods")
async def compare_periods(
    body: ComparePeriodRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.compare_periods(body.period_labels)


@owb_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_workload_report().model_dump()


@owb_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
