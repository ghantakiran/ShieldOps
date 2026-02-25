"""Cloud Savings Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.savings_tracker import (
    SavingsSource,
    SavingsStatus,
    TrackingPeriod,
)

logger = structlog.get_logger()
st_route = APIRouter(
    prefix="/savings-tracker",
    tags=["Savings Tracker"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Savings tracker unavailable")
    return _tracker


class RecordSavingsRequest(BaseModel):
    source: SavingsSource = SavingsSource.RIGHT_SIZING
    service_name: str
    team: str
    projected_savings: float = 0.0
    realized_savings: float = 0.0
    period: TrackingPeriod = TrackingPeriod.MONTHLY
    start_date: str = ""
    end_date: str = ""


class CreateGoalRequest(BaseModel):
    team: str
    target_amount: float
    period: TrackingPeriod = TrackingPeriod.MONTHLY


class UpdateRealizedRequest(BaseModel):
    amount: float


@st_route.post("/records")
async def record_savings(
    body: RecordSavingsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    record = tracker.record_savings(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@st_route.get("/records")
async def list_records(
    source: SavingsSource | None = None,
    status: SavingsStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in tracker.list_records(
            source=source,
            status=status,
            limit=limit,
        )
    ]


@st_route.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    record = tracker.get_record(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@st_route.put("/records/{record_id}/realized")
async def update_realized(
    record_id: str,
    body: UpdateRealizedRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    record = tracker.update_realized(
        record_id,
        body.amount,
    )
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@st_route.post("/goals")
async def create_goal(
    body: CreateGoalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    goal = tracker.create_goal(
        body.team,
        body.target_amount,
        body.period,
    )
    return goal.model_dump()  # type: ignore[no-any-return]


@st_route.get("/realization-rate")
async def get_realization_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return {  # type: ignore[no-any-return]
        "realization_rate_pct": (tracker.calculate_realization_rate()),
    }


@st_route.get("/rankings")
async def get_rankings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.rank_teams_by_savings()  # type: ignore[no-any-return]


@st_route.get("/missed")
async def get_missed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [  # type: ignore[no-any-return]
        r.model_dump() for r in tracker.identify_missed_opportunities()
    ]


@st_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.generate_savings_report().model_dump()  # type: ignore[no-any-return]


@st_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    tracker = _get_tracker()
    tracker.clear_data()
    return {"status": "cleared"}


@st_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()  # type: ignore[no-any-return]
