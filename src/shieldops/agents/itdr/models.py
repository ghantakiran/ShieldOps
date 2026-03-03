"""State models for the ITDRRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IdentityScanResult(BaseModel):
    """A identity scan result result."""

    scan_id: str = ""
    identity_source: str = ""
    identities_scanned: int = 0
    anomalies_found: int = 0


class IdentityThreat(BaseModel):
    """A identity threat result."""

    threat_id: str = ""
    threat_type: str = ""
    severity: str = "medium"
    identity: str = ""
    confidence: float = 0.0


class AttackPath(BaseModel):
    """A attack path result."""

    path_id: str = ""
    source_identity: str = ""
    target_resource: str = ""
    hops: int = 0
    risk_score: float = 0.0


class ITDRReasoningStep(BaseModel):
    """Audit trail entry for the itdr workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class ITDRState(BaseModel):
    """Full state for a itdr workflow run through the LangGraph workflow."""

    session_id: str = ""
    detection_config: dict[str, Any] = Field(default_factory=dict)
    scan_results: list[IdentityScanResult] = Field(default_factory=list)
    identity_threats: list[IdentityThreat] = Field(default_factory=list)
    attack_paths: list[AttackPath] = Field(default_factory=list)
    threat_count: int = 0
    critical_count: int = 0
    response_actions: list[dict[str, Any]] = Field(default_factory=list)
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ITDRReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
