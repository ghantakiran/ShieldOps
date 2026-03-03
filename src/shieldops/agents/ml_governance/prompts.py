"""LLM prompt templates and response schemas for the ML Governance Agent."""

from pydantic import BaseModel, Field


class AuditOutput(BaseModel):
    """Structured output for model auditing."""

    audit_count: int = Field(description="Number of models audited")
    compliance_summary: str = Field(description="Summary of compliance findings")
    risk_level: str = Field(description="Overall risk level: critical/high/medium/low")


class FairnessOutput(BaseModel):
    """Structured output for fairness evaluation."""

    findings: list[dict[str, str]] = Field(
        description="Fairness findings with metric, severity, description",
    )
    fairness_score: float = Field(description="Overall fairness score 0-100")
    reasoning: str = Field(description="Fairness evaluation reasoning")


class ActionPlanOutput(BaseModel):
    """Structured output for action planning."""

    actions: list[dict[str, str]] = Field(
        description="Governance actions with priority and target",
    )
    estimated_effort: str = Field(description="Estimated remediation effort")
    reasoning: str = Field(description="Action planning reasoning")


SYSTEM_AUDIT = """\
You are an expert ML governance analyst performing model auditing.

Given the audit configuration and model scope:
1. Identify all deployed ML models requiring governance review
2. Classify models by risk level and compliance status
3. Assess initial governance posture for each model

Focus on: model bias, fairness metrics, data lineage, compliance certifications."""


SYSTEM_EVALUATE = """\
You are an expert ML governance analyst evaluating model fairness.

Given the model audits and their compliance data:
1. Evaluate fairness metrics across protected attributes
2. Assess demographic parity and equalized odds violations
3. Map findings to relevant compliance frameworks

Prioritize findings that indicate discriminatory outcomes or regulatory violations."""


SYSTEM_ACT = """\
You are an expert ML governance analyst planning remediation actions.

Given the governance findings and their severity:
1. Prioritize remediation actions by risk reduction impact
2. Identify quick wins vs long-term governance improvements
3. Estimate effort and compliance dependencies

Balance speed of remediation with model operational impact."""
