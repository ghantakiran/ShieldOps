"""State models for the Investigation Agent."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shieldops.models.base import AlertContext, Hypothesis, RemediationAction


class LogFinding(BaseModel):
    """A notable finding from log analysis."""

    source: str  # splunk, cloudwatch, etc.
    query: str
    summary: str
    severity: str  # error, warning, info
    sample_entries: list[str] = Field(default_factory=list, max_length=10)
    count: int = 0
    time_range: str = ""


class MetricAnomaly(BaseModel):
    """An anomaly detected in metrics."""

    metric_name: str
    source: str  # prometheus, datadog, cloudwatch
    current_value: float
    baseline_value: float
    deviation_percent: float
    started_at: datetime
    labels: dict[str, str] = Field(default_factory=dict)


class TraceResult(BaseModel):
    """Result from distributed trace analysis."""

    trace_id: str
    root_service: str
    bottleneck_service: str | None = None
    error_service: str | None = None
    total_duration_ms: float
    spans: list[dict[str, Any]] = Field(default_factory=list)


class CorrelatedEvent(BaseModel):
    """An event correlated across multiple sources."""

    timestamp: datetime
    source: str
    event_type: str
    description: str
    related_resources: list[str] = Field(default_factory=list)
    correlation_score: float = Field(ge=0.0, le=1.0)


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning chain."""

    step_number: int
    action: str  # query_logs, analyze_metrics, correlate, hypothesize, etc.
    input_summary: str
    output_summary: str
    duration_ms: int
    tool_used: str | None = None


class HistoricalPattern(BaseModel):
    """A pattern matched from historical incident data."""

    incident_id: str
    alert_type: str
    root_cause: str
    resolution_action: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    was_correct: bool = True
    environment: str = ""


class InvestigationState(BaseModel):
    """Full state of an investigation workflow (LangGraph state)."""

    # Input
    alert_id: str
    alert_context: AlertContext

    # Investigation findings
    log_findings: list[LogFinding] = Field(default_factory=list)
    metric_anomalies: list[MetricAnomaly] = Field(default_factory=list)
    trace_analysis: TraceResult | None = None
    correlated_events: list[CorrelatedEvent] = Field(default_factory=list)
    historical_patterns: list[HistoricalPattern] = Field(default_factory=list)

    # Outputs
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    confidence_score: float = 0.0
    recommended_action: RemediationAction | None = None

    # Metadata
    investigation_start: datetime | None = None
    investigation_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
