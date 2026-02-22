"""Security posture dashboard API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/security/posture", tags=["Security Posture"])

_aggregator: Any = None


def set_aggregator(agg: Any) -> None:
    global _aggregator
    _aggregator = agg


@router.get("/overview")
async def posture_overview(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _aggregator is None:
        raise HTTPException(status_code=501, detail="Security posture not configured")
    result: dict[str, Any] = await _aggregator.get_overview()
    return result


@router.get("/trends")
async def posture_trends(
    days: int = 30,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _aggregator is None:
        raise HTTPException(status_code=501, detail="Security posture not configured")
    result: dict[str, Any] = await _aggregator.get_trends(days=days)
    return result


@router.get("/risk-matrix")
async def risk_matrix(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _aggregator is None:
        raise HTTPException(status_code=501, detail="Security posture not configured")
    result: dict[str, Any] = await _aggregator.get_risk_matrix()
    return result


@router.get("/team/{team_id}")
async def team_posture(
    team_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _aggregator is None:
        raise HTTPException(status_code=501, detail="Security posture not configured")
    result: dict[str, Any] = await _aggregator.get_team_posture(team_id)
    return result
