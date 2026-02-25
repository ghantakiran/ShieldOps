"""Handoff Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.handoff_tracker import HandoffType

logger = structlog.get_logger()
ht_route = APIRouter(
    prefix="/handoff-tracker",
    tags=["Handoff Tracker"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Handoff tracker unavailable")
    return _tracker


class RecordHandoffRequest(BaseModel):
    incident_id: str
    from_responder: str
    to_responder: str
    handoff_type: HandoffType = HandoffType.SHIFT_CHANGE
    delay_minutes: float = 0.0
    notes_provided: bool = False
    runbook_attached: bool = False


@ht_route.post("/handoffs")
async def record_handoff(
    body: RecordHandoffRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    record = tracker.record_handoff(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@ht_route.get("/handoffs")
async def list_handoffs(
    incident_id: str | None = None,
    handoff_type: HandoffType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in tracker.list_handoffs(
            incident_id=incident_id,
            handoff_type=handoff_type,
            limit=limit,
        )
    ]


@ht_route.get("/handoffs/{record_id}")
async def get_handoff(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    record = tracker.get_handoff(record_id)
    if record is None:
        raise HTTPException(404, f"Handoff '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@ht_route.post("/handoffs/{record_id}/assess")
async def assess_quality(
    record_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.assess_quality(record_id)  # type: ignore[no-any-return]


@ht_route.get("/patterns")
async def detect_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    patterns = tracker.detect_patterns()
    return [p.model_dump() for p in patterns]  # type: ignore[no-any-return]


@ht_route.get("/problem-pairs")
async def identify_problem_pairs(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.identify_problem_pairs()  # type: ignore[no-any-return]


@ht_route.get("/avg-delay")
async def calculate_avg_delay(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.calculate_avg_delay()  # type: ignore[no-any-return]


@ht_route.get("/information-loss")
async def rank_by_information_loss(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.rank_by_information_loss()  # type: ignore[no-any-return]


@ht_route.get("/report")
async def generate_handoff_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.generate_handoff_report().model_dump()  # type: ignore[no-any-return]


@ht_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()  # type: ignore[no-any-return]


@ht_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    tracker = _get_tracker()
    tracker.clear_data()
    return {"status": "cleared"}
