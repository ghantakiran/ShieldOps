"""Pydantic models for deep health check endpoints."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(enum.StrEnum):
    """Possible health states for a component or the overall platform."""

    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"
    unknown = "unknown"


class ComponentHealth(BaseModel):
    """Health snapshot for a single platform component."""

    name: str = Field(description="Component identifier")
    status: HealthStatus = Field(description="Current health status")
    latency_ms: float = Field(description="Round-trip check latency in milliseconds")
    last_check: datetime = Field(description="Timestamp of the most recent health check")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary component-specific metadata",
    )
    error: str | None = Field(
        default=None,
        description="Error message when the check failed",
    )


class DeepHealthResponse(BaseModel):
    """Aggregated health report across all platform components."""

    status: HealthStatus = Field(description="Overall platform health")
    components: list[ComponentHealth] = Field(description="Per-component health details")
    uptime_seconds: float = Field(description="Seconds since the API process started")
    version: str = Field(description="Running platform version")
    checked_at: datetime = Field(description="Timestamp when this deep check was performed")
