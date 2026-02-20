"""API usage analytics endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from shieldops.api.auth.dependencies import (
    get_current_user,
    require_role,
)
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.middleware.usage_tracker import get_usage_tracker

router = APIRouter()


@router.get("/analytics/api-usage")
async def get_api_usage(
    hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Lookback window",
    ),
    org_id: str | None = Query(
        default=None,
        description="Filter by organization",
    ),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Overall API usage statistics."""
    tracker = get_usage_tracker()
    return tracker.get_usage(org_id=org_id, hours=hours)


@router.get("/analytics/api-usage/endpoints")
async def get_top_endpoints(
    hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Lookback window",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Max results",
    ),
    org_id: str | None = Query(
        default=None,
        description="Filter by organization",
    ),
    _user: UserResponse = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Top endpoints by call volume."""
    tracker = get_usage_tracker()
    return tracker.get_top_endpoints(
        org_id=org_id,
        limit=limit,
        hours=hours,
    )


@router.get("/analytics/api-usage/hourly")
async def get_hourly_volume(
    hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Lookback window",
    ),
    org_id: str | None = Query(
        default=None,
        description="Filter by organization",
    ),
    _user: UserResponse = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Hourly call volume for charting."""
    tracker = get_usage_tracker()
    return tracker.get_hourly_breakdown(
        org_id=org_id,
        hours=hours,
    )


@router.get("/analytics/api-usage/by-org")
async def get_usage_by_org(
    hours: int = Query(
        default=24,
        ge=1,
        le=720,
        description="Lookback window",
    ),
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN),
    ),
) -> list[dict[str, Any]]:
    """Per-organization API usage breakdown (admin only)."""
    tracker = get_usage_tracker()
    return tracker.get_usage_by_org(hours=hours)
