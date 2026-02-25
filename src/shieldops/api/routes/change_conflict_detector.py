"""Change conflict detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
ccd_route = APIRouter(
    prefix="/change-conflict-detector",
    tags=["Change Conflict Detector"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Change conflict detector service unavailable",
        )
    return _instance


# -- Request models --


class RegisterChangeRequest(BaseModel):
    change_name: str
    service_name: str = ""
    owner: str = ""
    start_at: float = 0.0
    end_at: float = 0.0
    resources: list[str] = []
    dependencies: list[str] = []


class ResolveConflictRequest(BaseModel):
    conflict_id: str
    resolution: str = "manual_coordination"


# -- Routes --


@ccd_route.post("/changes")
async def register_change(
    body: RegisterChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    change = engine.register_change(**body.model_dump())
    return change.model_dump()


@ccd_route.get("/changes")
async def list_changes(
    service_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        c.model_dump()
        for c in engine.list_changes(
            service_name=service_name,
            status=status,
            limit=limit,
        )
    ]


@ccd_route.get("/changes/{change_id}")
async def get_change(
    change_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    change = engine.get_change(change_id)
    if change is None:
        raise HTTPException(404, f"Change '{change_id}' not found")
    return change.model_dump()


@ccd_route.post("/detect/{change_id}")
async def detect_conflicts(
    change_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    conflicts = engine.detect_conflicts(change_id)
    return [c.model_dump() for c in conflicts]


@ccd_route.post("/detect-all")
async def detect_all_conflicts(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    conflicts = engine.detect_all_conflicts()
    return [c.model_dump() for c in conflicts]


@ccd_route.get("/conflicts")
async def list_conflicts(
    severity: str | None = None,
    conflict_type: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        c.model_dump()
        for c in engine.list_conflicts(
            severity=severity,
            conflict_type=conflict_type,
            limit=limit,
        )
    ]


@ccd_route.get("/conflicts/{conflict_id}")
async def get_conflict(
    conflict_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    conflict = engine.get_conflict(conflict_id)
    if conflict is None:
        raise HTTPException(404, f"Conflict '{conflict_id}' not found")
    return conflict.model_dump()


@ccd_route.post("/resolve")
async def resolve_conflict(
    body: ResolveConflictRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.resolve_conflict(body.conflict_id, body.resolution)
    if not result:
        raise HTTPException(404, f"Conflict '{body.conflict_id}' not found")
    return {"resolved": True, "conflict_id": body.conflict_id}


@ccd_route.get("/reschedule/{conflict_id}")
async def suggest_reschedule(
    conflict_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.suggest_reschedule(conflict_id)


@ccd_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_conflict_report().model_dump()


@ccd_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
