"""LLM prompt templates and response schemas for the ObservabilityIntelligence Agent."""

from pydantic import BaseModel, Field


class CollectOutput(BaseModel):
    """Structured output for collect_output."""

    signal_count: int = Field(description="Number of signals collected")
    source_count: int = Field(description="Number of sources accessed")


class AnalysisOutput(BaseModel):
    """Structured output for analysis_output."""

    insight_count: int = Field(description="Number of insights generated")
    confidence: float = Field(description="Analysis confidence 0-100")
    reasoning: str = Field(description="Analysis reasoning")


SYSTEM_COLLECT = """\
You are an expert observability signal collector.

Given the observability configuration:
1. Identify all relevant signal sources
2. Collect metrics, logs, and traces
3. Validate signal quality and completeness

Prioritize high-fidelity signals."""

SYSTEM_ANALYZE = """\
You are an expert observability analyst.

Given the correlated signals:
1. Identify patterns and anomalies
2. Assess system health across dimensions
3. Generate actionable recommendations

Balance depth with actionability."""
