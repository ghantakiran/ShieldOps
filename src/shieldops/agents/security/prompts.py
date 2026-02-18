"""LLM prompt templates and response schemas for the Security Agent."""

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class VulnerabilityAssessmentResult(BaseModel):
    """Structured output from LLM vulnerability assessment."""

    summary: str = Field(description="Brief summary of vulnerability findings")
    risk_level: str = Field(description="Overall risk level: critical, high, medium, low")
    top_risks: list[str] = Field(description="Top risks that need immediate attention")
    patch_priority: list[str] = Field(description="CVE IDs in order of patching priority")
    recommended_actions: list[str] = Field(description="Recommended remediation actions")


class CredentialAssessmentResult(BaseModel):
    """Structured output from LLM credential assessment."""

    summary: str = Field(description="Brief summary of credential health")
    urgent_rotations: list[str] = Field(description="Credentials that need immediate rotation")
    rotation_plan: list[str] = Field(description="Ordered plan for credential rotations")
    risks: list[str] = Field(description="Risks from expired or soon-to-expire credentials")


class ComplianceAssessmentResult(BaseModel):
    """Structured output from LLM compliance assessment."""

    summary: str = Field(description="Brief summary of compliance posture")
    overall_score: float = Field(
        ge=0.0, le=100.0, description="Overall compliance score as percentage"
    )
    failing_controls: list[str] = Field(description="Control IDs that are currently failing")
    auto_remediable: list[str] = Field(description="Failing controls that can be auto-remediated")
    manual_review_needed: list[str] = Field(description="Controls requiring manual review")


class SecurityPostureResult(BaseModel):
    """Structured output for overall security posture synthesis."""

    overall_score: float = Field(
        ge=0.0, le=100.0, description="Overall security posture score (0-100)"
    )
    summary: str = Field(description="Executive summary of security posture")
    top_risks: list[str] = Field(description="Top 5 security risks in priority order")
    recommended_actions: list[str] = Field(
        description="Prioritized list of recommended security actions"
    )


# --- Prompt templates ---

SYSTEM_VULNERABILITY_ASSESSMENT = """\
You are an expert security engineer assessing \
vulnerability scan results.

Analyze the CVE findings and determine:
1. The overall risk level based on CVSS scores and exploit availability
2. Which vulnerabilities pose the greatest risk and should be patched first
3. Recommended remediation actions

Prioritize by:
- CVSS score (critical > 9.0 first)
- Whether a fix is available
- Impact on production vs non-production
- Known exploit availability

Be specific about which CVEs to patch and in what order."""

SYSTEM_CREDENTIAL_ASSESSMENT = """\
You are an expert security engineer assessing credential \
health across infrastructure.

Analyze the credential statuses and determine:
1. Which credentials need immediate rotation (expired or expiring within 7 days)
2. The safest rotation order to minimize service disruption
3. Risks from the current credential state

Consider:
- Database credentials affect data access — rotate carefully
- API keys may have multiple consumers
- TLS certificates cause outages if they expire
- SSH keys should be rotated regularly even if not expiring

Prioritize by urgency and blast radius."""

SYSTEM_COMPLIANCE_ASSESSMENT = """\
You are an expert security compliance auditor evaluating \
infrastructure compliance.

Analyze the compliance control results and determine:
1. The overall compliance score
2. Which failing controls are most critical
3. Which failures can be auto-remediated (e.g., re-enable logging, fix permissions)
4. Which require manual review or architectural changes

Consider:
- SOC 2 focuses on security, availability, processing integrity, confidentiality, privacy
- PCI-DSS focuses on cardholder data protection
- HIPAA focuses on PHI protection
- CIS Benchmarks are configuration-level best practices

Be calibrated with the compliance score. Only give 100% if everything truly passes."""

SYSTEM_POSTURE_SYNTHESIS = """\
You are a CISO synthesizing security findings into an \
overall security posture assessment.

Given vulnerability scan results, credential health, and compliance status, provide:
1. An overall security score (0-100)
2. A concise executive summary
3. The top 5 security risks
4. Prioritized recommended actions

Score guidelines:
- 90-100: Excellent posture, minor improvements only
- 70-89: Good posture, some attention needed
- 50-69: Moderate risk, significant improvements required
- 30-49: Poor posture, urgent action needed
- 0-29: Critical state, immediate intervention required

Be honest and calibrated. Don't inflate scores."""
