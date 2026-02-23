"""Secret rotation scheduling API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/secret-rotation", tags=["Secret Rotation"])

_scheduler: Any = None


def set_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


def _get_scheduler() -> Any:
    if _scheduler is None:
        raise HTTPException(503, "Secret rotation service unavailable")
    return _scheduler


class RegisterSecretRequest(BaseModel):
    name: str
    secret_type: str
    service: str
    environment: str = "production"
    rotation_interval_days: int = 90
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartRotationRequest(BaseModel):
    initiated_by: str = ""


class CompleteRotationRequest(BaseModel):
    success: bool = True
    error_message: str = ""


@router.post("/secrets")
async def register_secret(
    body: RegisterSecretRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    secret = scheduler.register_secret(**body.model_dump())
    return secret.model_dump()


@router.get("/secrets")
async def list_secrets(
    service: str | None = None,
    secret_type: str | None = None,
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [
        s.model_dump()
        for s in scheduler.list_secrets(service=service, secret_type=secret_type, status=status)
    ]


@router.get("/secrets/overdue")
async def get_overdue_secrets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [s.model_dump() for s in scheduler.get_overdue_secrets()]


@router.get("/secrets/{secret_id}")
async def get_secret(
    secret_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    secret = scheduler.get_secret(secret_id)
    if secret is None:
        raise HTTPException(404, f"Secret '{secret_id}' not found")
    return secret.model_dump()


@router.delete("/secrets/{secret_id}")
async def delete_secret(
    secret_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    removed = scheduler.delete_secret(secret_id)
    if not removed:
        raise HTTPException(404, f"Secret '{secret_id}' not found")
    return {"deleted": True, "secret_id": secret_id}


@router.post("/rotations/{secret_id}/start")
async def start_rotation(
    secret_id: str,
    body: StartRotationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    event = scheduler.start_rotation(secret_id, **body.model_dump())
    return event.model_dump()


@router.put("/rotations/{event_id}/complete")
async def complete_rotation(
    event_id: str,
    body: CompleteRotationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    event = scheduler.complete_rotation(event_id, **body.model_dump())
    return event.model_dump()


@router.get("/rotations")
async def get_rotation_history(
    secret_id: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scheduler = _get_scheduler()
    return [e.model_dump() for e in scheduler.get_rotation_history(secret_id=secret_id)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scheduler = _get_scheduler()
    return scheduler.get_stats()
