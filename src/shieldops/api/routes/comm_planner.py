"""Incident Communication Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.comm_planner import (
    Audience,
    CommCadence,
    CommChannel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/comm-planner",
    tags=["Incident Communication Planner"],
)

_instance: Any = None


def set_planner(planner: Any) -> None:
    global _instance
    _instance = planner


def _get_planner() -> Any:
    if _instance is None:
        raise HTTPException(503, "Communication planner unavailable")
    return _instance


class CreatePlanRequest(BaseModel):
    incident_id: str = ""
    audience: Audience = Audience.ENGINEERING
    channel: CommChannel = CommChannel.SLACK
    cadence: CommCadence = CommCadence.HOURLY
    template: str = ""


class SendMessageRequest(BaseModel):
    plan_id: str
    content: str
    sent_by: str = ""


@router.post("/plans")
async def create_plan(
    body: CreatePlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    plan = planner.create_plan(**body.model_dump())
    return plan.model_dump()


@router.post("/messages")
async def send_message(
    body: SendMessageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    msg = planner.send_message(
        plan_id=body.plan_id,
        content=body.content,
        sent_by=body.sent_by,
    )
    if msg is None:
        raise HTTPException(404, "Plan not found")
    return msg.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.get_stats()


@router.get("/report")
async def get_comm_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.generate_comm_report().model_dump()


@router.get("/overdue")
async def get_overdue_comms(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return planner.check_overdue_comms()


@router.get("/gaps")
async def get_communication_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return planner.detect_communication_gaps()


@router.get("/response-times")
async def get_response_times(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.analyze_response_times()


@router.get("/coverage/{incident_id}")
async def get_comm_coverage(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    return planner.calculate_comm_coverage(incident_id)


@router.get("/plans")
async def list_plans(
    incident_id: str | None = None,
    audience: Audience | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    planner = _get_planner()
    return [
        p.model_dump()
        for p in planner.list_plans(
            incident_id=incident_id,
            audience=audience,
            limit=limit,
        )
    ]


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    planner = _get_planner()
    plan = planner.get_plan(plan_id)
    if plan is None:
        raise HTTPException(404, f"Plan '{plan_id}' not found")
    return plan.model_dump()
