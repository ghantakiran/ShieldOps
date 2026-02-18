"""LLM prompt templates and response schemas for the Cost Agent."""

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class CostAnomalyAssessmentResult(BaseModel):
    """Structured output from LLM cost anomaly assessment."""

    summary: str = Field(description="Brief summary of cost anomalies detected")
    critical_anomalies: list[str] = Field(description="Resource IDs with critical cost anomalies")
    root_causes: list[str] = Field(description="Likely root causes for the biggest cost anomalies")
    immediate_actions: list[str] = Field(
        description="Actions to take immediately to reduce anomalous spending"
    )


class OptimizationAssessmentResult(BaseModel):
    """Structured output from LLM optimization assessment."""

    summary: str = Field(description="Brief summary of optimization opportunities")
    top_recommendations: list[str] = Field(
        description="Top optimization recommendations by savings potential"
    )
    quick_wins: list[str] = Field(
        description="Optimizations that can be implemented with low effort"
    )
    estimated_total_monthly_savings: float = Field(
        ge=0.0, description="Total estimated monthly savings across all recommendations"
    )


class CostForecastResult(BaseModel):
    """Structured output for cost forecasting and savings synthesis."""

    overall_health_score: float = Field(
        ge=0.0, le=100.0, description="Overall cost health score (0-100, higher is better)"
    )
    summary: str = Field(description="Executive summary of cost posture")
    monthly_forecast: float = Field(
        ge=0.0, description="Projected monthly spend at current trajectory"
    )
    top_cost_risks: list[str] = Field(description="Top cost risks in priority order")
    recommended_actions: list[str] = Field(
        description="Prioritized list of cost optimization actions"
    )


# --- Prompt templates ---

SYSTEM_COST_ANOMALY_ASSESSMENT = """\
You are an expert FinOps engineer analyzing cloud \
cost anomalies.

Analyze the cost anomaly data and determine:
1. Which anomalies are most critical and need immediate attention
2. Likely root causes (misconfiguration, traffic spike, resource leak, etc.)
3. Immediate actions to reduce anomalous spending

Prioritize by:
- Deviation magnitude (highest cost overruns first)
- Service criticality (production > staging > development)
- Whether the anomaly is ongoing vs. resolved
- Ease of remediation

Be specific about which resources need attention and what actions to take."""

SYSTEM_OPTIMIZATION_ASSESSMENT = """\
You are an expert FinOps engineer identifying cloud cost \
optimization opportunities.

Analyze the resource utilization and cost data to identify:
1. Unused or underutilized resources that can be downsized or terminated
2. Rightsizing opportunities based on actual usage vs. provisioned capacity
3. Reserved instance or savings plan opportunities
4. Scheduling opportunities (dev/staging resources running 24/7 unnecessarily)
5. Architecture improvements that could reduce costs

For each recommendation, consider:
- Monthly savings potential
- Implementation effort (low/medium/high)
- Risk to service reliability
- Whether it can be automated

Prioritize quick wins (high savings, low effort) first."""

SYSTEM_COST_FORECAST = """\
You are a FinOps leader synthesizing cloud cost analysis \
into an executive summary.

Given resource costs, anomalies, and optimization opportunities, provide:
1. A cost health score (0-100, where 100 = fully optimized)
2. A concise executive summary
3. Monthly spend forecast at current trajectory
4. Top cost risks
5. Prioritized recommended actions

Score guidelines:
- 90-100: Excellent cost management, minimal waste
- 70-89: Good cost hygiene, some optimization opportunities
- 50-69: Moderate waste, significant savings available
- 30-49: Poor cost management, urgent optimization needed
- 0-29: Critical overspend, immediate intervention required

Be honest and data-driven. Don't ignore anomalies or understate savings potential."""
