"""State models for the Attack Surface Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DiscoveredAsset(BaseModel):
    """An asset discovered during attack surface scanning."""

    asset_id: str = ""
    asset_type: str = ""
    hostname: str = ""
    ip_address: str = ""
    exposure_level: str = "low"
    risk_score: float = 0.0


class ExposureFinding(BaseModel):
    """A security exposure finding."""

    finding_id: str = ""
    finding_type: str = ""
    severity: str = "medium"
    affected_asset: str = ""
    description: str = ""
    remediation: str = ""


class SurfaceReasoningStep(BaseModel):
    """Audit trail entry for the attack surface workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class AttackSurfaceState(BaseModel):
    """Full state for an attack surface workflow run through the LangGraph workflow."""

    # Input
    scan_id: str = ""
    scan_config: dict[str, Any] = Field(default_factory=dict)

    # Discovery
    discovered_assets: list[DiscoveredAsset] = Field(default_factory=list)
    asset_count: int = 0

    # Analysis
    exposure_findings: list[ExposureFinding] = Field(default_factory=list)
    risk_score: float = 0.0

    # Prioritization
    prioritized_findings: list[dict[str, Any]] = Field(default_factory=list)
    critical_count: int = 0

    # Remediation
    remediation_plan: list[dict[str, Any]] = Field(default_factory=list)
    remediation_started: bool = False

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[SurfaceReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
