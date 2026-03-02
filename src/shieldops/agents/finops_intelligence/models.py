"""State models for the FinOps Intelligence Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CostFinding(BaseModel):
    """A cost anomaly or waste finding."""

    finding_id: str = ""
    finding_type: str = ""
    category: str = ""
    amount: float = 0.0
    service: str = ""
    team: str = ""


class OptimizationOpportunity(BaseModel):
    """A cost optimization opportunity."""

    opportunity_id: str = ""
    opportunity_type: str = ""
    severity: str = "medium"
    affected_resource: str = ""
    description: str = ""
    estimated_savings: float = 0.0


class FinOpsReasoningStep(BaseModel):
    """Audit trail entry for the FinOps Intelligence workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class FinOpsIntelligenceState(BaseModel):
    """Full state for a FinOps Intelligence workflow run."""

    # Input
    session_id: str = ""
    analysis_config: dict[str, Any] = Field(default_factory=dict)

    # Cost analysis
    cost_findings: list[CostFinding] = Field(default_factory=list)
    finding_count: int = 0

    # Optimization
    optimization_opportunities: list[OptimizationOpportunity] = Field(default_factory=list)
    savings_potential: float = 0.0

    # Prioritization
    prioritized_actions: list[dict[str, Any]] = Field(default_factory=list)
    high_impact_count: int = 0

    # Implementation
    implementation_plan: list[dict[str, Any]] = Field(default_factory=list)
    plan_started: bool = False

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[FinOpsReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
