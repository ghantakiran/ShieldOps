"""Pydantic response models for the ShieldOps API."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Paginated response wrapper
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response returned by list endpoints."""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0

    @property
    def has_more(self) -> bool:
        """Return True when further pages exist."""
        return self.offset + self.limit < self.total


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------


class Investigation(BaseModel):
    """Investigation summary returned by the API."""

    investigation_id: str
    alert_id: str
    alert_name: str = ""
    status: str = "pending"
    severity: str = ""
    confidence: float = 0.0
    hypotheses_count: int = 0
    duration_ms: int = 0
    error: str | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------


class Remediation(BaseModel):
    """Remediation record returned by the API."""

    id: str = Field(alias="remediation_id", default="")
    action_type: str = ""
    target_resource: str = ""
    environment: str = ""
    status: str = "pending"
    risk_level: str = ""
    description: str = ""
    created_at: datetime | None = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Security scan
# ---------------------------------------------------------------------------


class SecurityScan(BaseModel):
    """Security scan summary."""

    scan_id: str = ""
    scan_type: str = ""
    status: str = "pending"
    environment: str = ""
    compliance_score: float = 0.0
    critical_cves: int = 0
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Vulnerability
# ---------------------------------------------------------------------------


class Vulnerability(BaseModel):
    """Vulnerability record from the vulnerability management system."""

    id: str = ""
    cve_id: str = ""
    severity: str = ""
    status: str = "new"
    affected_resource: str = ""
    scanner_type: str = ""
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent(BaseModel):
    """Agent fleet entry."""

    id: str = Field(alias="agent_id", default="")
    agent_type: str = ""
    status: str = ""
    environment: str = ""
    last_heartbeat: datetime | None = None

    model_config = {"populate_by_name": True}
