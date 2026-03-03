"""State models for the Threat Automation Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DetectedThreat(BaseModel):
    """A threat detected during automated hunting."""

    threat_id: str = ""
    threat_type: str = ""
    severity: str = "medium"
    source: str = ""
    confidence: float = 0.0
    indicators: list[str] = Field(default_factory=list)


class BehaviorAnalysis(BaseModel):
    """A behavioral analysis result."""

    analysis_id: str = ""
    behavior_type: str = ""
    risk_score: float = 0.0
    anomalies: list[str] = Field(default_factory=list)
    verdict: str = "benign"


class IntelCorrelation(BaseModel):
    """A threat intelligence correlation result."""

    correlation_id: str = ""
    intel_source: str = ""
    matched_indicators: int = 0
    campaign: str = ""
    confidence: float = 0.0


class ThreatReasoningStep(BaseModel):
    """Audit trail entry for the threat automation workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class ThreatAutomationState(BaseModel):
    """Full state for a threat automation workflow run through the LangGraph workflow."""

    # Input
    hunt_id: str = ""
    hunt_config: dict[str, Any] = Field(default_factory=dict)

    # Detection
    detected_threats: list[DetectedThreat] = Field(default_factory=list)
    threat_count: int = 0

    # Behavior analysis
    behavior_analyses: list[BehaviorAnalysis] = Field(default_factory=list)

    # Intelligence correlation
    intel_correlations: list[IntelCorrelation] = Field(default_factory=list)

    # Response
    critical_count: int = 0
    response_actions: list[dict[str, Any]] = Field(default_factory=list)
    automated_responses: int = 0

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ThreatReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
