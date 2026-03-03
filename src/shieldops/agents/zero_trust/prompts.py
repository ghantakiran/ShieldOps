"""LLM prompt templates and response schemas for the Zero Trust Agent."""

from pydantic import BaseModel, Field


class IdentityVerificationOutput(BaseModel):
    """Structured output for identity verification."""

    verified_count: int = Field(description="Number of identities verified")
    risk_summary: str = Field(description="Summary of identity risk findings")
    trust_level: str = Field(description="Overall trust level: high/medium/low/none")


class DeviceAssessmentOutput(BaseModel):
    """Structured output for device posture assessment."""

    devices: list[dict[str, str]] = Field(
        description="Device assessments with id, type, posture, compliance",
    )
    compliance_score: float = Field(description="Overall compliance score 0-100")
    issues: list[str] = Field(description="List of device posture issues found")


class PolicyEnforcementOutput(BaseModel):
    """Structured output for policy enforcement."""

    actions: list[dict[str, str]] = Field(
        description="Enforcement actions with type, target, and status",
    )
    enforced_count: int = Field(description="Number of policies enforced")
    reasoning: str = Field(description="Enforcement reasoning and justification")


SYSTEM_VERIFY = """\
You are an expert zero trust security analyst performing identity verification.

Given the assessment configuration and identity context:
1. Verify all identities using multi-factor authentication signals
2. Assess identity risk based on behavioral patterns and anomalies
3. Calculate trust scores for each verified identity

Focus on: MFA status, session anomalies, privilege escalation, credential freshness."""


SYSTEM_ASSESS = """\
You are an expert zero trust security analyst assessing device posture.

Given the verified identities and device telemetry:
1. Evaluate device compliance against security baselines
2. Check for missing patches, outdated software, and misconfigurations
3. Assess device health and integrity signals

Prioritize devices with elevated access or non-compliant configurations."""


SYSTEM_ENFORCE = """\
You are an expert zero trust security analyst enforcing access policies.

Given the identity verifications, device assessments, and access violations:
1. Determine appropriate enforcement actions for each violation
2. Apply least-privilege principles to access decisions
3. Generate remediation recommendations for policy gaps

Balance security enforcement with operational continuity."""
