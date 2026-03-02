"""State models for the Threat Hunter Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HuntFinding(BaseModel):
    """A single finding from a threat hunt activity."""

    source: str = ""
    query: str = ""
    summary: str = ""
    severity: str = "low"
    confidence: float = 0.0


class ReasoningStep(BaseModel):
    """Audit trail entry for the threat hunter workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class ThreatHunterState(BaseModel):
    """Full state for a threat hunter workflow run through the LangGraph workflow."""

    # Input
    hypothesis_id: str = ""
    hypothesis: str = ""
    hunt_scope: dict[str, Any] = Field(default_factory=dict)
    data_sources: list[str] = Field(default_factory=list)

    # Hunt results
    ioc_sweep_results: list[dict[str, Any]] = Field(default_factory=list)
    behavioral_findings: list[dict[str, Any]] = Field(default_factory=list)
    mitre_findings: list[dict[str, Any]] = Field(default_factory=list)

    # Correlation & assessment
    correlated_findings: list[dict[str, Any]] = Field(default_factory=list)
    threat_assessment: dict[str, Any] = Field(default_factory=dict)
    response_recommendations: list[dict[str, Any]] = Field(default_factory=list)

    # Outcome
    threat_found: bool = False
    effectiveness_score: float = 0.0

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
