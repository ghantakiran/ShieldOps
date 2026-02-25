"""Config Change Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.config_change_tracker import (
    ChangeApproval,
    ChangeImpact,
    ChangeScope,
)

logger = structlog.get_logger()
cct_route = APIRouter(
    prefix="/config-change-tracker",
    tags=["Config Change Tracker"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Config change tracker unavailable")
    return _tracker


class RecordChangeRequest(BaseModel):
    service_name: str
    scope: ChangeScope = ChangeScope.APPLICATION
    key: str
    old_value: str = ""
    new_value: str = ""
    author: str = ""
    approval: ChangeApproval = ChangeApproval.PENDING
    impact: ChangeImpact = ChangeImpact.NONE


class RollbackRequest(BaseModel):
    actor: str
    reason: str


class AuditRequest(BaseModel):
    action: str
    actor: str
    reason: str


@cct_route.post("/changes")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    change = tracker.record_change(**body.model_dump())
    return change.model_dump()  # type: ignore[no-any-return]


@cct_route.get("/changes")
async def list_changes(
    service_name: str | None = None,
    scope: ChangeScope | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [  # type: ignore[no-any-return]
        c.model_dump()
        for c in tracker.list_changes(
            service_name=service_name,
            scope=scope,
            limit=limit,
        )
    ]


@cct_route.get("/changes/{change_id}")
async def get_change(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    change = tracker.get_change(change_id)
    if change is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return change.model_dump()  # type: ignore[no-any-return]


@cct_route.post("/changes/{change_id}/rollback")
async def rollback_change(
    change_id: str,
    body: RollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    change = tracker.rollback_change(
        change_id,
        body.actor,
        body.reason,
    )
    if change is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return change.model_dump()  # type: ignore[no-any-return]


@cct_route.post("/changes/{change_id}/audit")
async def audit_change(
    change_id: str,
    body: AuditRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    trail = tracker.audit_change(
        change_id,
        body.action,
        body.actor,
        body.reason,
    )
    return trail.model_dump()  # type: ignore[no-any-return]


@cct_route.get("/rollback-rate")
async def get_rollback_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return {"rollback_rate_pct": tracker.calculate_rollback_rate()}  # type: ignore[no-any-return]


@cct_route.get("/unauthorized")
async def get_unauthorized_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [  # type: ignore[no-any-return]
        c.model_dump() for c in tracker.detect_unauthorized_changes()
    ]


@cct_route.get("/correlated")
async def get_correlated_changes(
    time_window_minutes: int = 30,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[list[dict[str, Any]]]:
    tracker = _get_tracker()
    clusters = tracker.find_correlated_changes(
        time_window_minutes,
    )
    return [  # type: ignore[no-any-return]
        [c.model_dump() for c in cluster] for cluster in clusters
    ]


@cct_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.generate_tracker_report().model_dump()  # type: ignore[no-any-return]


@cct_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    tracker = _get_tracker()
    tracker.clear_data()
    return {"status": "cleared"}


@cct_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()  # type: ignore[no-any-return]
