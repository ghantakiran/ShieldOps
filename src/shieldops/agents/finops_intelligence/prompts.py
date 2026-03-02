"""LLM prompt templates and response schemas for the FinOps Intelligence Agent."""

from pydantic import BaseModel, Field


class CostAnalysisOutput(BaseModel):
    """Structured output for cost analysis."""

    finding_count: int = Field(description="Number of cost findings identified")
    cost_summary: str = Field(description="Summary of cost anomalies and waste")
    risk_level: str = Field(description="Overall risk level: critical/high/medium/low")


class OptimizationOutput(BaseModel):
    """Structured output for optimization identification."""

    opportunities: list[dict[str, str]] = Field(
        description="Optimization opportunities with type, severity, description",
    )
    savings_potential: float = Field(description="Total estimated savings potential in USD")
    reasoning: str = Field(description="Optimization reasoning")


class ImplementationPlanOutput(BaseModel):
    """Structured output for implementation planning."""

    actions: list[dict[str, str]] = Field(
        description="Implementation actions with priority and target",
    )
    estimated_effort: str = Field(description="Estimated implementation effort")
    reasoning: str = Field(description="Implementation reasoning")


SYSTEM_ANALYZE = """\
You are an expert FinOps analyst performing cloud cost analysis.

Given the analysis configuration and cloud spend data:
1. Identify cost anomalies, spikes, and unexpected charges
2. Detect idle or underutilized resources
3. Surface waste across compute, storage, network, and data transfer

Focus on: spend by service, team attribution, budget variance, and anomalies."""


SYSTEM_OPTIMIZE = """\
You are an expert FinOps analyst identifying cost optimization opportunities.

Given the cost findings and resource utilization data:
1. Identify rightsizing opportunities for compute and storage
2. Recommend reserved instance or savings plan purchases
3. Detect data transfer inefficiencies and optimization paths

Prioritize opportunities by estimated savings and implementation complexity."""


SYSTEM_PLAN = """\
You are an expert FinOps analyst creating implementation plans.

Given the optimization opportunities and their priorities:
1. Sequence implementation actions to minimize operational risk
2. Identify quick wins vs long-term structural changes
3. Estimate effort, dependencies, and expected ROI

Balance speed of savings realization with operational stability."""
