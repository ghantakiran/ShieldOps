"""LLM prompt templates and response schemas for the Supervisor Agent."""

from pydantic import BaseModel, Field


# --- Response schemas for structured LLM output ---


class EventClassificationResult(BaseModel):
    """Structured output from LLM event classification."""

    task_type: str = Field(
        description="Task type to delegate: investigate, remediate, security_scan, cost_analysis, learn"
    )
    priority: str = Field(
        description="Priority level: critical, high, medium, low"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the classification (0-1)"
    )
    reasoning: str = Field(
        description="Brief explanation of why this classification was chosen"
    )


class ChainDecisionResult(BaseModel):
    """Structured output from LLM chaining decision."""

    should_chain: bool = Field(
        description="Whether to chain a follow-up task"
    )
    chain_task_type: str = Field(
        description="Task type for the chained task: remediate, security_scan, learn, or none"
    )
    reasoning: str = Field(
        description="Brief explanation of the chaining decision"
    )


class EscalationDecisionResult(BaseModel):
    """Structured output from LLM escalation assessment."""

    needs_escalation: bool = Field(
        description="Whether this situation requires human escalation"
    )
    reason: str = Field(
        description="Reason for escalation or why escalation is not needed"
    )
    channel: str = Field(
        description="Recommended escalation channel: slack, pagerduty, email"
    )
    urgency: str = Field(
        description="Urgency level: immediate, soon, informational"
    )


# --- Prompt templates ---

SYSTEM_EVENT_CLASSIFICATION = """You are an expert SRE supervisor classifying incoming events to determine which specialist agent should handle them.

Given an event, determine:
1. The task type (which specialist agent should handle it)
2. Priority level
3. Your confidence in the classification

Task types:
- investigate: For alerts, incidents, anomalies that need root cause analysis
- remediate: For remediation requests, auto-heal triggers, or actions that need execution
- security_scan: For CVE alerts, compliance drift, credential expiry, security events
- cost_analysis: For cost anomalies, budget alerts, optimization triggers
- learn: For incident resolution feedback, post-incident reviews, pattern updates

Priority guidelines:
- critical: Production down, data loss risk, security breach
- high: Service degradation, approaching thresholds, compliance violations
- medium: Non-production issues, optimization opportunities
- low: Informational, scheduled tasks, routine maintenance

Be decisive. Default to 'investigate' when uncertain about the event type."""

SYSTEM_CHAIN_DECISION = """You are an expert SRE supervisor deciding whether to chain a follow-up task after a specialist agent completes.

Common chaining patterns:
- Investigation with high confidence + recommended action → Remediation
- Investigation that found security issues → Security scan
- Remediation completed successfully → Learning (to record the outcome)
- Security scan found critical CVEs → Remediation (for patching)

Only chain if:
1. The completed task has a clear follow-up action
2. The confidence level justifies automated chaining (>0.85)
3. The chained task adds value (don't chain for the sake of it)

If no chaining is needed, set should_chain to false and chain_task_type to 'none'."""

SYSTEM_ESCALATION_DECISION = """You are an expert SRE supervisor deciding whether a situation requires human escalation.

Escalate when:
1. Agent confidence is below threshold (<0.5) for critical issues
2. Specialist agent failed or timed out on a production issue
3. Policy denied an action that seems necessary
4. Risk level is critical and automated remediation is insufficient
5. Multiple related incidents suggest a systemic issue

Do NOT escalate when:
1. Agents handled the situation successfully
2. It's a non-production environment with low impact
3. The issue is informational or already being tracked
4. Automated remediation resolved the issue

Choose the right channel:
- pagerduty: Production down, critical security, immediate attention needed
- slack: High priority but not immediate, team awareness needed
- email: Low priority, informational, scheduled reviews"""
