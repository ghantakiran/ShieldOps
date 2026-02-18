"""LLM prompt templates and response schemas for the Learning Agent."""

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class PatternAnalysisResult(BaseModel):
    """Structured output from LLM pattern analysis."""

    summary: str = Field(description="Brief summary of patterns found in incident data")
    recurring_patterns: list[str] = Field(description="Descriptions of recurring incident patterns")
    common_root_causes: list[str] = Field(description="Most frequent root causes across incidents")
    automation_gaps: list[str] = Field(
        description="Areas where automation could improve but currently doesn't"
    )


class PlaybookRecommendationResult(BaseModel):
    """Structured output from LLM playbook recommendation."""

    summary: str = Field(description="Brief summary of playbook recommendations")
    new_playbooks: list[str] = Field(
        description="New playbooks to create, each as 'alert_type: description'"
    )
    playbook_improvements: list[str] = Field(description="Improvements to existing playbooks")
    deprecated_steps: list[str] = Field(
        description="Playbook steps that should be removed or updated"
    )


class ThresholdRecommendationResult(BaseModel):
    """Structured output from LLM threshold analysis."""

    summary: str = Field(description="Brief summary of threshold recommendations")
    adjustments: list[str] = Field(
        description="Recommended threshold changes, each as "
        "'metric: current → recommended (reason)'"
    )
    estimated_noise_reduction: float = Field(
        ge=0.0, le=100.0, description="Estimated percentage reduction in alert noise"
    )


class ImprovementSynthesisResult(BaseModel):
    """Structured output for overall improvement synthesis."""

    improvement_score: float = Field(
        ge=0.0, le=100.0, description="Overall improvement score (0-100)"
    )
    summary: str = Field(description="Executive summary of learning cycle findings")
    key_improvements: list[str] = Field(description="Top improvements identified in priority order")
    risks: list[str] = Field(description="Risks if recommendations are not implemented")


# --- Prompt templates ---

SYSTEM_PATTERN_ANALYSIS = """\
You are an expert SRE analyzing incident patterns \
to identify systemic issues.

Analyze the incident outcome data and identify:
1. Recurring incident patterns (same alert type, same root cause, similar symptoms)
2. Common root causes across different incident types
3. Areas where automated remediation could be improved
4. Gaps in current automation coverage

Look for:
- Incidents that repeat on a regular cadence (indicating unfixed underlying issues)
- Similar root causes across different alert types
- Cases where automated actions were incorrect (indicating model drift)
- Resolution time trends (getting faster or slower?)

Be specific about which incidents support each pattern you identify."""

SYSTEM_PLAYBOOK_RECOMMENDATION = """\
You are an expert SRE creating operational playbook \
recommendations.

Based on the incident patterns and outcomes, recommend:
1. New playbooks for recurring incident types that lack automated responses
2. Improvements to existing playbooks based on what actually works
3. Steps that should be deprecated because they're no longer effective

For each recommendation:
- Be specific about the alert type and conditions
- Include concrete steps (not generic advice)
- Prioritize by incident frequency and impact
- Consider whether the playbook can be fully automated

Focus on actionable improvements, not theoretical best practices."""

SYSTEM_THRESHOLD_RECOMMENDATION = """\
You are an expert SRE analyzing alerting thresholds to \
reduce noise and improve signal quality.

Based on the incident data, recommend threshold adjustments:
1. Thresholds that are too sensitive (causing false positives)
2. Thresholds that are too loose (missing real incidents)
3. New thresholds that should be added based on observed patterns

For each recommendation:
- Specify the metric and current threshold
- Recommend a new threshold with reasoning
- Estimate the impact on false positive rate
- Consider different environments (production vs staging)

Be conservative — it's better to catch real incidents with some noise than to miss them."""

SYSTEM_IMPROVEMENT_SYNTHESIS = """\
You are an SRE leader synthesizing learning cycle \
findings into an improvement plan.

Given pattern analysis, playbook recommendations, and threshold adjustments, provide:
1. An overall improvement score (0-100)
2. A concise executive summary
3. Top improvements in priority order
4. Risks if recommendations are not implemented

Score guidelines:
- 90-100: Strong continuous improvement, minimal gaps
- 70-89: Good learning cycle, clear actionable improvements
- 50-69: Moderate improvements needed, some recurring issues
- 30-49: Significant gaps, many recurring incidents
- 0-29: Critical improvement needed, automation not learning effectively

Focus on measurable improvements and concrete next steps."""
