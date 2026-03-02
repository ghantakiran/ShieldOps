"""State models for the SOC Analyst Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ThreatIntelEnrichment(BaseModel):
    """Threat intelligence enrichment data for an alert."""

    ioc_matches: list[str] = Field(default_factory=list)
    threat_feeds: list[str] = Field(default_factory=list)
    reputation_score: float = 0.0
    geo_ip_info: dict[str, Any] = Field(default_factory=dict)
    related_campaigns: list[str] = Field(default_factory=list)


class CorrelatedEvent(BaseModel):
    """An event correlated with the primary alert."""

    event_id: str = ""
    event_type: str = ""
    source: str = ""
    timestamp: str = ""
    summary: str = ""
    severity: str = "low"
    relevance_score: float = 0.0


class ContainmentRecommendation(BaseModel):
    """A containment action recommendation."""

    action: str = ""
    target: str = ""
    urgency: str = "medium"
    risk_level: str = "low"
    automated: bool = False
    description: str = ""


class ReasoningStep(BaseModel):
    """Audit trail entry for the SOC analyst workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class SOCAnalystState(BaseModel):
    """Full state for a SOC analyst workflow run through the LangGraph workflow."""

    # Input
    alert_id: str = ""
    alert_data: dict[str, Any] = Field(default_factory=dict)

    # Triage
    tier: int = 1  # 1, 2, or 3
    triage_score: float = 0.0
    should_suppress: bool = False

    # Enrichment
    threat_intel_enrichment: ThreatIntelEnrichment | None = None
    asset_context: dict[str, Any] = Field(default_factory=dict)

    # Correlation
    correlated_events: list[CorrelatedEvent] = Field(default_factory=list)

    # MITRE ATT&CK
    mitre_techniques: list[str] = Field(default_factory=list)

    # Attack chain
    attack_chain: list[dict[str, Any]] = Field(default_factory=list)
    attack_narrative: str = ""

    # Containment
    containment_recommendations: list[ContainmentRecommendation] = Field(default_factory=list)
    playbook_executed: bool = False
    playbook_result: dict[str, Any] = Field(default_factory=dict)

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
