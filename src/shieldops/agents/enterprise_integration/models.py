"""State models for the Enterprise Integration Agent."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IntegrationStatus(StrEnum):
    """Health status of an enterprise integration."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    CONFIGURING = "configuring"
    ERROR = "error"


class IntegrationDirection(StrEnum):
    """Data flow direction for an integration."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class IntegrationCategory(StrEnum):
    """Functional category of the integration."""

    COMMUNICATION = "communication"
    MONITORING = "monitoring"
    SECURITY = "security"
    DEVOPS = "devops"
    TICKETING = "ticketing"
    CLOUD = "cloud"
    ITSM = "itsm"


class RateLimitConfig(BaseModel):
    """Rate-limit configuration for an integration endpoint."""

    requests_per_minute: int = 60
    burst_limit: int = 10


class RetryPolicy(BaseModel):
    """Retry behaviour when an integration request fails."""

    max_retries: int = 3
    backoff_seconds: float = 1.0


class IntegrationConfig(BaseModel):
    """Configuration for a single enterprise integration."""

    id: str
    name: str
    provider: str = Field(
        description=(
            "Integration provider: slack, teams, pagerduty, jira, github, "
            "datadog, splunk, crowdstrike, servicenow, opsgenie, prometheus, sentinel"
        ),
    )
    category: IntegrationCategory
    direction: IntegrationDirection
    endpoint_url: str
    auth_type: str = Field(
        description="Authentication type: oauth2, api_key, service_account, webhook",
    )
    scopes: list[str] = Field(default_factory=list)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    health_check_interval_seconds: int = 60
    enabled: bool = True


class IntegrationHealth(BaseModel):
    """Point-in-time health snapshot for an integration."""

    integration_id: str
    status: IntegrationStatus
    last_health_check: datetime
    last_successful_sync: datetime | None = None
    error_message: str | None = None
    error_count_1h: int = 0
    latency_ms: float = 0.0
    events_today: int = 0
    uptime_percent_24h: float = 100.0


class SyncEvent(BaseModel):
    """Record of a single data-sync operation."""

    id: str
    integration_id: str
    direction: IntegrationDirection
    event_type: str
    payload_summary: str
    status: str  # success, failed, partial
    timestamp: datetime
    duration_ms: int = 0
    error: str | None = None


class DiagnosticFinding(BaseModel):
    """A single diagnostic finding during integration analysis."""

    severity: str  # critical, error, warning, info
    component: str
    finding: str
    recommendation: str


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning chain."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int
    tool_used: str | None = None


class IntegrationState(BaseModel):
    """Full state of an integration workflow (LangGraph state)."""

    # Input
    integration_id: str
    action: str = Field(
        description="Requested action: health_check, sync, configure, diagnose, reconnect",
    )

    # Processing
    config: IntegrationConfig | None = None
    health: IntegrationHealth | None = None
    sync_events: list[SyncEvent] = Field(default_factory=list)
    diagnostics: list[DiagnosticFinding] = Field(default_factory=list)

    # Output
    result: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    status_changed: bool = False

    # Metadata
    action_start: datetime | None = None
    processing_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
