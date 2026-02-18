"""State models for the Cost Agent LangGraph workflow."""

from datetime import datetime

from pydantic import BaseModel, Field

from shieldops.models.base import Environment


class ResourceCost(BaseModel):
    """Cost data for a single infrastructure resource."""

    resource_id: str
    resource_type: str  # instance, pod, storage, network, database, etc.
    service: str  # e.g. EC2, RDS, GKE, S3
    environment: Environment
    provider: str  # aws, gcp, azure, kubernetes
    daily_cost: float = 0.0
    monthly_cost: float = 0.0
    currency: str = "USD"
    usage_percent: float = 0.0  # how utilized is the resource (0-100)
    tags: dict[str, str] = Field(default_factory=dict)


class CostAnomaly(BaseModel):
    """A detected cost anomaly."""

    resource_id: str
    service: str
    anomaly_type: str  # spike, drift, unused, oversized
    severity: str  # critical, high, medium, low
    expected_daily_cost: float
    actual_daily_cost: float
    deviation_percent: float  # how much above/below expected
    started_at: datetime | None = None
    description: str = ""


class OptimizationRecommendation(BaseModel):
    """A cost optimization recommendation."""

    id: str
    category: str  # rightsizing, unused_resources, reserved_instances, scheduling, architecture
    resource_id: str
    service: str
    current_monthly_cost: float
    projected_monthly_cost: float
    monthly_savings: float
    confidence: float = Field(ge=0.0, le=1.0)
    effort: str = "low"  # low, medium, high
    description: str = ""
    implementation_steps: list[str] = Field(default_factory=list)


class CostSavings(BaseModel):
    """Summary of realized and potential cost savings."""

    period: str = "30d"
    total_monthly_spend: float = 0.0
    optimized_monthly_spend: float = 0.0
    total_potential_savings: float = 0.0
    savings_by_category: dict[str, float] = Field(default_factory=dict)
    hours_saved_by_automation: float = 0.0
    automation_savings_usd: float = 0.0
    engineer_hourly_rate: float = 75.0


class CostStep(BaseModel):
    """Audit trail entry for cost analysis workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str = ""


class CostAnalysisState(BaseModel):
    """Full state for a cost analysis run through the LangGraph workflow."""

    analysis_id: str = ""
    analysis_type: str = "full"  # full, anomaly_only, optimization_only, savings_only
    target_environment: Environment = Environment.PRODUCTION
    target_services: list[str] = Field(default_factory=list)
    period: str = "30d"

    # Gathered data
    resource_costs: list[ResourceCost] = Field(default_factory=list)
    total_daily_spend: float = 0.0
    total_monthly_spend: float = 0.0
    spend_by_service: dict[str, float] = Field(default_factory=dict)
    spend_by_environment: dict[str, float] = Field(default_factory=dict)

    # Anomaly detection
    cost_anomalies: list[CostAnomaly] = Field(default_factory=list)
    critical_anomaly_count: int = 0

    # Optimization
    optimization_recommendations: list[OptimizationRecommendation] = Field(default_factory=list)
    total_potential_savings: float = 0.0

    # Savings summary
    cost_savings: CostSavings | None = None

    # Workflow tracking
    analysis_start: datetime | None = None
    analysis_duration_ms: int = 0
    reasoning_chain: list[CostStep] = Field(default_factory=list)
    current_step: str = "pending"
    error: str | None = None
