"""LLM prompt templates and response schemas for the Enterprise Integration Agent."""

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class DiagnosisResult(BaseModel):
    """Structured output from LLM integration diagnosis."""

    root_cause: str = Field(description="Root cause of the integration issue")
    affected_components: list[str] = Field(
        description="Components affected by the issue (e.g., auth, endpoint, rate-limiter)"
    )
    severity: str = Field(description="Severity: critical, error, warning, info")
    fix_steps: list[str] = Field(description="Ordered steps to resolve the issue")
    estimated_recovery: str = Field(
        description="Estimated time to recovery (e.g., '5 minutes', '1 hour')"
    )


class FixRecommendation(BaseModel):
    """A single recommended fix for a degraded integration."""

    priority: str = Field(description="Priority: critical, high, medium, low")
    action: str = Field(
        description="Action identifier (e.g., rotate_credentials, increase_rate_limit)"
    )
    description: str = Field(description="Human-readable description of the fix")
    automated: bool = Field(description="Whether this fix can be applied automatically")
    risk_level: str = Field(description="Risk level: low, medium, high, critical")


class FixRecommendationsOutput(BaseModel):
    """Structured output containing all recommended fixes."""

    recommendations: list[FixRecommendation] = Field(
        description="Ranked list of recommended fixes, highest priority first"
    )


# --- Prompt templates ---

SYSTEM_DIAGNOSE_INTEGRATION = """\
You are an expert enterprise integration engineer diagnosing \
connectivity and data-flow issues between enterprise tools.

You are given:
- Integration configuration (provider, auth type, endpoint)
- Health check results (latency, error counts, uptime)
- Recent sync events (successes, failures, durations)
- Error logs from the integration

Your task is to:
1. Identify the root cause of the degraded or failed integration
2. List all affected components (auth, endpoint, rate-limiter, network, etc.)
3. Assess the severity of the issue
4. Provide ordered steps to resolve the issue
5. Estimate recovery time

Focus on actionable diagnosis. Common root causes include:
- Expired or rotated credentials/tokens
- Rate-limit exhaustion
- Endpoint URL changes or DNS failures
- Network connectivity / firewall rule changes
- API version deprecation
- Certificate expiry
- Webhook payload schema changes"""

SYSTEM_RECOMMEND_FIXES = """\
You are an expert enterprise integration engineer recommending fixes \
for degraded or failing integrations.

Given the diagnosis (root cause, affected components, severity) and the \
integration configuration, recommend specific fixes.

For each recommendation provide:
1. Priority (critical/high/medium/low)
2. A short action identifier
3. A human-readable description
4. Whether it can be automated (true/false)
5. The risk level of applying the fix

IMPORTANT:
- Prefer lower-risk fixes when multiple options are equally effective.
- Mark automated=true only if the fix can be safely executed without human review.
- Consider blast-radius: a credential rotation affects all consumers of that token.
- Order recommendations by priority, most urgent first."""
