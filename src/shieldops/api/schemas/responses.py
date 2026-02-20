"""Typed API response models for OpenAPI documentation.

These models provide a typed contract for all API responses, improving
auto-generated OpenAPI docs, enabling TypeScript type generation, and
serving as validation schemas that routes can adopt incrementally.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PaginatedResponse[T](BaseModel):
    """Standard paginated response wrapper."""

    items: list[T]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(examples=["healthy"])
    version: str = Field(examples=["1.0.0"])
    services: dict[str, str] = Field(default_factory=dict)


class InvestigationResponse(BaseModel):
    """Investigation detail response."""

    id: str
    alert_id: str
    alert_name: str = ""
    severity: str = "warning"
    status: str = "init"
    confidence: float = 0.0
    environment: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RemediationResponse(BaseModel):
    """Remediation detail response."""

    id: str
    action_type: str
    target_resource: str
    environment: str
    risk_level: str
    status: str = "init"
    validation_passed: bool | None = None
    investigation_id: str | None = None
    created_at: datetime | None = None


class SecurityScanResponse(BaseModel):
    """Security scan detail response."""

    id: str
    scan_type: str
    environment: str
    status: str = "init"
    compliance_score: float = 0.0
    critical_cve_count: int = 0
    patches_applied: int = 0
    credentials_rotated: int = 0
    created_at: datetime | None = None


class VulnerabilityResponse(BaseModel):
    """Vulnerability detail response."""

    id: str
    cve_id: str | None = None
    severity: str
    status: str = "new"
    title: str = ""
    affected_resource: str
    cvss_score: float = 0.0
    sla_breached: bool = False
    created_at: datetime | None = None


class AgentResponse(BaseModel):
    """Agent fleet member response."""

    id: str
    agent_type: str
    environment: str = "production"
    status: str = "idle"
    last_heartbeat: datetime | None = None


class AuditLogEntry(BaseModel):
    """Immutable audit log entry."""

    id: str
    timestamp: datetime
    agent_type: str
    action: str
    target_resource: str
    environment: str
    risk_level: str
    outcome: str
    actor: str


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    name: str
    role: str
    is_active: bool = True
    created_at: datetime | None = None


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str
