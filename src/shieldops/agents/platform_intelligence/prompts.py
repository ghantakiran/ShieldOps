"""LLM prompt templates and response schemas for the PlatformIntelligence Agent."""

from pydantic import BaseModel, Field


class IngestOutput(BaseModel):
    """Structured output for ingestoutput."""

    telemetry_count: int = Field(description="Number of telemetry items ingested")
    domain_count: int = Field(description="Number of domains covered")


class StrategyOutput(BaseModel):
    """Structured output for strategyoutput."""

    actions_count: int = Field(description="Number of strategy actions")
    confidence: float = Field(description="Strategy confidence 0-100")
    reasoning: str = Field(description="Strategy reasoning")


SYSTEM_GATHER = """\
You are an expert platform telemetry analyst.

Given the platform telemetry sources:
1. Collect data from all signal domains
2. Normalize and correlate signals
3. Identify key patterns and anomalies

Prioritize actionable insights over volume."""

SYSTEM_STRATEGY = """\
You are an expert platform optimization strategist.

Given the analysis results and context:
1. Generate optimization recommendations
2. Prioritize by impact and feasibility
3. Validate strategy coherence

Maximize platform health while minimizing risk."""
