"""Pydantic v2 models for the API gateway — keys, tenants, usage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class APIKeyStatus(StrEnum):
    """Lifecycle status of an API key."""

    active = "active"
    revoked = "revoked"
    expired = "expired"


class APIKeyScope(StrEnum):
    """Permission scopes assignable to an API key."""

    read = "read"
    write = "write"
    admin = "admin"
    agent_execute = "agent_execute"


class APIKey(BaseModel):
    """Metadata for a tenant API key (never stores the raw secret)."""

    key_id: str
    org_id: str
    name: str
    prefix: str = Field(
        ...,
        max_length=8,
        description="First 8 characters of the raw key for display",
    )
    hashed_key: str
    scopes: list[APIKeyScope]
    status: APIKeyStatus = APIKeyStatus.active
    rate_limit_per_minute: int = 60
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None


class TenantConfig(BaseModel):
    """Per-tenant gateway configuration tied to billing plan."""

    org_id: str
    plan: str = Field(
        default="free",
        pattern="^(free|starter|growth|enterprise)$",
    )
    rate_limit_per_minute: int = 60
    max_concurrent_agents: int = 1
    allowed_environments: list[str] = Field(default_factory=list)
    features_enabled: list[str] = Field(default_factory=list)


class APIUsageRecord(BaseModel):
    """Single API call usage record for analytics."""

    org_id: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    timestamp: datetime
    api_key_id: str | None = None
