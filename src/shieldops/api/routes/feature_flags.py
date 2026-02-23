"""Feature flag management API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.config.feature_flags import (
    FeatureFlag,
    FlagContext,
    FlagStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Feature flag service unavailable")
    return _manager


class CreateFlagRequest(BaseModel):
    name: str
    description: str = ""
    status: FlagStatus = FlagStatus.DISABLED
    rollout_percentage: float = 0.0
    target_org_ids: list[str] = []
    target_user_ids: list[str] = []
    variants: dict[str, Any] = {}
    default_variant: str = ""
    tags: list[str] = []


class UpdateFlagRequest(BaseModel):
    description: str | None = None
    status: FlagStatus | None = None
    rollout_percentage: float | None = None
    target_org_ids: list[str] | None = None
    target_user_ids: list[str] | None = None
    variants: dict[str, Any] | None = None
    default_variant: str | None = None


@router.get("")
async def list_feature_flags(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [f.model_dump() for f in mgr.list_flags()]


@router.post("")
async def create_feature_flag(
    body: CreateFlagRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    flag = FeatureFlag(**body.model_dump())
    return mgr.register(flag).model_dump()


@router.get("/{name}")
async def get_feature_flag(
    name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    flag = mgr.get(name)
    if flag is None:
        raise HTTPException(404, f"Flag '{name}' not found")
    return flag.model_dump()


@router.put("/{name}")
async def update_feature_flag(
    name: str,
    body: UpdateFlagRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    flag = mgr.update(name, updates)
    if flag is None:
        raise HTTPException(404, f"Flag '{name}' not found")
    return flag.model_dump()


@router.delete("/{name}")
async def delete_feature_flag(
    name: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, str]:
    mgr = _get_manager()
    if not mgr.delete(name):
        raise HTTPException(404, f"Flag '{name}' not found")
    return {"deleted": name}


@router.post("/{name}/evaluate")
async def evaluate_feature_flag(
    name: str,
    context: FlagContext | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    result = mgr.evaluate(name, context)
    return result.model_dump()


@router.post("/sync")
async def sync_feature_flags(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    count = await mgr.sync_to_redis()
    return {"synced": count}
