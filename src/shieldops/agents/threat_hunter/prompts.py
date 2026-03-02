"""LLM prompt templates and response schemas for the Threat Hunter Agent."""

from pydantic import BaseModel, Field


class HypothesisOutput(BaseModel):
    """Structured output for threat hypothesis generation."""

    hypothesis: str = Field(description="Threat hypothesis statement")
    data_sources: list[str] = Field(description="Data sources required for the hunt")
    mitre_techniques: list[str] = Field(description="MITRE ATT&CK technique IDs to investigate")
    confidence: float = Field(description="Confidence in the hypothesis 0-1")


class ThreatAssessmentOutput(BaseModel):
    """Structured output for threat assessment."""

    threat_found: bool = Field(description="Whether a confirmed threat was found")
    severity: str = Field(description="Threat severity: critical/high/medium/low")
    confidence: float = Field(description="Assessment confidence 0-1")
    summary: str = Field(description="Human-readable assessment summary")
    affected_assets: list[str] = Field(description="List of affected asset identifiers")


SYSTEM_HYPOTHESIS = """\
You are an expert threat hunter formulating a threat hunting hypothesis.

Given the available context (recent threat intel, environment profile, historical incidents):
1. Formulate a specific, testable hypothesis about potential adversary activity
2. Identify the data sources needed to validate or refute the hypothesis
3. Map the hypothesis to relevant MITRE ATT&CK techniques
4. Assess your initial confidence in the hypothesis

Focus on high-impact, low-visibility threats that automated detections may miss."""


SYSTEM_ASSESSMENT = """\
You are an expert threat hunter assessing correlated findings from a hunt campaign.

Given the IOC sweep results, behavioral analysis, and MITRE ATT&CK coverage findings:
1. Determine whether a confirmed threat exists
2. Assess severity based on potential impact and attacker capability
3. Identify all affected assets
4. Provide a clear summary for SOC analysts and incident responders

Be precise — distinguish between confirmed threats, suspicious activity, and benign anomalies."""
