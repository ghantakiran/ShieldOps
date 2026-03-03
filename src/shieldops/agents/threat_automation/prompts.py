"""LLM prompt templates and response schemas for the Threat Automation Agent."""

from pydantic import BaseModel, Field


class ThreatDetectionOutput(BaseModel):
    """Structured output for threat detection."""

    threat_count: int = Field(description="Number of threats detected")
    severity_summary: str = Field(description="Summary of threat severities")
    risk_level: str = Field(description="Overall risk level: critical/high/medium/low")


class BehaviorAnalysisOutput(BaseModel):
    """Structured output for behavior analysis."""

    analyses: list[dict[str, str]] = Field(
        description="Behavior analyses with type, risk_score, verdict",
    )
    risk_score: float = Field(description="Overall behavioral risk score 0-100")
    reasoning: str = Field(description="Analysis reasoning")


class ResponseAutomationOutput(BaseModel):
    """Structured output for response automation."""

    actions: list[dict[str, str]] = Field(
        description="Response actions with type, target, and status",
    )
    automated_count: int = Field(description="Number of automated response actions executed")
    reasoning: str = Field(description="Response automation reasoning")


SYSTEM_DETECT = """\
You are an expert threat hunter performing automated threat detection.

Given the hunt configuration and telemetry sources:
1. Identify active threats and suspicious activity patterns
2. Classify threat types and assess severity levels
3. Extract indicators of compromise (IOCs) for each detected threat

Focus on: network anomalies, endpoint behaviors, authentication patterns,
data exfiltration signals."""


SYSTEM_ANALYZE = """\
You are an expert threat analyst performing behavioral analysis.

Given the detected threats and their indicators:
1. Analyze behavioral patterns and anomalies
2. Correlate behaviors across multiple data sources
3. Determine threat actor tactics, techniques, and procedures (TTPs)

Prioritize analysis of behaviors that indicate active compromise or lateral movement."""


SYSTEM_RESPOND = """\
You are an expert incident responder automating threat response actions.

Given the detected threats and intelligence correlations:
1. Determine appropriate automated response actions
2. Prioritize containment of critical threats
3. Execute response playbooks with minimal operational impact

Balance speed of response with blast radius and false positive risk."""
