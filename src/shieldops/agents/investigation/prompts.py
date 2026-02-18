"""LLM prompt templates and response schemas for the Investigation Agent."""

from typing import Any

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class LogAnalysisResult(BaseModel):
    """Structured output from LLM log analysis."""

    summary: str = Field(description="Brief summary of what the logs indicate")
    error_patterns: list[str] = Field(
        description="Distinct error patterns found (e.g., 'connection timeout to db-main')"
    )
    severity: str = Field(description="Overall severity: critical, error, warning, info")
    root_cause_hints: list[str] = Field(description="Possible root cause hints from log analysis")
    affected_services: list[str] = Field(description="Services mentioned or implicated in the logs")


class MetricAnalysisResult(BaseModel):
    """Structured output from LLM metric analysis."""

    summary: str = Field(description="Brief summary of metric health")
    anomalies_detected: list[str] = Field(description="Human-readable descriptions of each anomaly")
    resource_pressure: str = Field(
        description="Overall resource pressure: none, low, moderate, high, critical"
    )
    likely_bottleneck: str | None = Field(
        description="The most likely resource bottleneck (cpu, memory, network, disk, connections)"
    )


class CorrelationResult(BaseModel):
    """Structured output from LLM cross-source correlation."""

    timeline: list[str] = Field(description="Ordered timeline of events leading to the incident")
    causal_chain: str = Field(
        description="Narrative of the causal chain (A caused B which caused C)"
    )
    correlated_events: list[str] = Field(
        description="Events across sources that are temporally/causally related"
    )
    key_evidence: list[str] = Field(description="The strongest pieces of evidence from all sources")


class HypothesisResult(BaseModel):
    """Structured output for a single root cause hypothesis."""

    description: str = Field(description="Clear description of the hypothesized root cause")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: list[str] = Field(description="Evidence supporting this hypothesis")
    affected_resources: list[str] = Field(description="Resources affected by this root cause")
    recommended_action: str | None = Field(
        description="Recommended remediation action type (e.g., restart_pod, scale_horizontal)"
    )
    reasoning: list[str] = Field(description="Step-by-step reasoning for this hypothesis")


class HypothesesOutput(BaseModel):
    """Structured output containing all hypotheses."""

    hypotheses: list[HypothesisResult] = Field(
        description="Ranked list of root cause hypotheses, most confident first"
    )


class RecommendedActionOutput(BaseModel):
    """Structured output for a remediation recommendation."""

    action_type: str = Field(
        description="Action type: restart_pod, scale_horizontal, rollback_deployment, "
        "increase_memory_limit, increase_connection_pool, rotate_credentials"
    )
    target_resource: str = Field(description="Resource to act on (e.g., namespace/pod-name)")
    description: str = Field(description="Human-readable description of what this action does")
    risk_level: str = Field(description="Risk level: low, medium, high, critical")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters (e.g., replicas count, memory limit)",
    )
    estimated_duration_seconds: int = Field(description="Estimated time to complete the action")


# --- Prompt templates ---

SYSTEM_LOG_ANALYSIS = """\
You are an expert SRE analyzing application logs \
during an incident investigation.

Your task is to analyze the provided log entries and identify:
1. Error patterns that could indicate the root cause
2. The severity of the situation
3. Any hints about what's causing the issue
4. Services that are affected

Be specific about error messages and patterns you find. Focus on actionable findings."""

SYSTEM_METRIC_ANALYSIS = """\
You are an expert SRE analyzing infrastructure metrics \
during an incident investigation.

Your task is to analyze metric data and anomalies to identify:
1. Which metrics show abnormal behavior
2. The overall resource pressure level
3. The most likely bottleneck (CPU, memory, network, disk, connections)
4. Whether the metrics support or contradict the log findings

Focus on anomalies that deviate significantly from baseline values."""

SYSTEM_CORRELATION = """\
You are an expert SRE correlating findings from multiple \
data sources during an incident investigation.

You are given:
- Log analysis findings (errors, patterns)
- Metric anomalies (deviations from baseline)
- Kubernetes events (pod restarts, failures)
- Trace analysis (if available)

Your task is to:
1. Build a timeline of events that led to the incident
2. Identify the causal chain (what caused what)
3. Find correlations across different data sources
4. Highlight the strongest pieces of evidence

Think step by step about temporal relationships and causality."""

SYSTEM_HYPOTHESIS_GENERATION = """\
You are an expert SRE generating root cause hypotheses \
for an infrastructure incident.

You are given the full investigation context including \
log findings, metric anomalies, correlated events, \
and alert context.

Generate ranked hypotheses with:
1. A clear description of the suspected root cause
2. A confidence score (0.0-1.0) based on strength of evidence
3. The specific evidence supporting each hypothesis
4. Affected resources
5. A recommended remediation action if confidence is high enough

IMPORTANT:
- Be calibrated with confidence scores. Only assign > 0.85 if evidence is very strong.
- Consider multiple possible explanations, not just the obvious one.
- Each hypothesis should be actionable — suggest what to do about it."""

SYSTEM_RECOMMEND_ACTION = """\
You are an expert SRE recommending a specific remediation \
action for a diagnosed infrastructure issue.

Given the top hypothesis and evidence, recommend the safest and most effective remediation action.

Consider:
- What action directly addresses the root cause
- The risk level (prefer lower-risk actions when equally effective)
- Whether the action is reversible
- How long it will take

Be specific about parameters (e.g., scale to how many replicas, what memory limit)."""
