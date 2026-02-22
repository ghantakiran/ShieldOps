"""Attack surface mapping API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/security/attack-surface", tags=["Attack Surface"])

_mapper: Any = None


def set_mapper(m: Any) -> None:
    global _mapper
    _mapper = m


@router.get("/map")
async def get_attack_surface(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _mapper is None:
        raise HTTPException(status_code=501, detail="Attack surface mapping not configured")
    result = await _mapper.map()
    data: dict[str, Any] = result.model_dump()
    return data


@router.get("/changes")
async def get_changes(
    since_hours: int = 24,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _mapper is None:
        raise HTTPException(status_code=501, detail="Attack surface mapping not configured")
    result: dict[str, Any] = await _mapper.get_changes(since_hours)
    return result


@router.get("/external-services")
async def get_external_services(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, list[dict[str, Any]]]:
    if _mapper is None:
        raise HTTPException(status_code=501, detail="Attack surface mapping not configured")
    services: list[dict[str, Any]] = await _mapper.get_external_services()
    return {"services": services}


@router.get("/risk-summary")
async def get_risk_summary(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _mapper is None:
        raise HTTPException(status_code=501, detail="Attack surface mapping not configured")
    result: dict[str, Any] = await _mapper.get_risk_summary()
    return result
