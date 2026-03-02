"""LLM prompt templates and response schemas for the Attack Surface Agent."""

from pydantic import BaseModel, Field


class DiscoveryOutput(BaseModel):
    """Structured output for asset discovery."""

    asset_count: int = Field(description="Number of assets discovered")
    exposure_summary: str = Field(description="Summary of exposed assets")
    risk_level: str = Field(description="Overall risk level: critical/high/medium/low")


class ExposureAnalysisOutput(BaseModel):
    """Structured output for exposure analysis."""

    findings: list[dict[str, str]] = Field(
        description="Exposure findings with type, severity, description",
    )
    risk_score: float = Field(description="Overall risk score 0-100")
    reasoning: str = Field(description="Analysis reasoning")


class RemediationPlanOutput(BaseModel):
    """Structured output for remediation planning."""

    actions: list[dict[str, str]] = Field(
        description="Remediation actions with priority and target",
    )
    estimated_effort: str = Field(description="Estimated remediation effort")
    reasoning: str = Field(description="Remediation reasoning")


SYSTEM_DISCOVER = """\
You are an expert attack surface analyst performing asset discovery.

Given the scan configuration and target scope:
1. Identify all externally visible assets
2. Classify asset types and exposure levels
3. Assess initial risk for each discovered asset

Focus on: DNS records, certificate transparency, cloud assets, API endpoints."""


SYSTEM_ANALYZE = """\
You are an expert attack surface analyst assessing security exposures.

Given the discovered assets and their configurations:
1. Identify security exposures and misconfigurations
2. Assess severity and exploitability
3. Map findings to relevant CVEs and threat vectors

Prioritize findings that could lead to unauthorized access or data exposure."""


SYSTEM_REMEDIATE = """\
You are an expert attack surface analyst planning remediation.

Given the exposure findings and their severity:
1. Prioritize remediation actions by risk reduction impact
2. Identify quick wins vs long-term fixes
3. Estimate effort and dependencies

Balance speed of remediation with operational impact."""
