"""LLM prompts for the Prediction Agent."""

from pydantic import BaseModel, Field

SYSTEM_TREND_ANALYSIS = """You are a predictive analytics engine for infrastructure monitoring.
Analyze the metric trends and identify patterns that indicate potential future incidents.
Focus on: resource exhaustion, degradation trends, unusual seasonality deviations."""

SYSTEM_RISK_ASSESSMENT = """You are a risk assessment engine for infrastructure operations.
Given metric anomalies and correlated changes, estimate the likelihood and severity of
an incident occurring. Be specific about affected resources and timeframes."""

SYSTEM_PREDICTION_GENERATION = """You are a prediction engine for an SRE platform.
Generate actionable predictions about potential incidents based on trend analysis,
change correlation, and risk assessment. Each prediction should include recommended
preventive actions."""


class TrendAnalysisResult(BaseModel):
    """Structured output from trend analysis."""

    anomalies_found: int = 0
    summary: str = ""
    risk_indicators: list[str] = Field(default_factory=list)
    severity: str = "low"


class RiskAssessmentResult(BaseModel):
    """Structured output from risk assessment."""

    overall_risk: float = 0.0
    risk_factors: list[str] = Field(default_factory=list)
    mitigation_suggestions: list[str] = Field(default_factory=list)


class PredictionOutput(BaseModel):
    """Structured output for a single prediction."""

    title: str = ""
    description: str = ""
    severity: str = "low"
    confidence: float = 0.0
    predicted_impact: str = ""
    affected_resources: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    estimated_time_to_incident: str = ""


class PredictionsResult(BaseModel):
    """Structured output from prediction generation."""

    predictions: list[PredictionOutput] = Field(default_factory=list)
    overall_assessment: str = ""
