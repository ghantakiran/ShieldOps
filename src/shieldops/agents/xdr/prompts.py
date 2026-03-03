"""LLM prompt templates and response schemas for the XDR Agent."""

from pydantic import BaseModel, Field


class IngestOutput(BaseModel):
    """Structured output for ingest_output."""

    telemetry_count: int = Field(description="Number of telemetry items ingested")
    domain_count: int = Field(description="Number of domains covered")


class ResponseOutput(BaseModel):
    """Structured output for response_output."""

    actions_count: int = Field(description="Number of response actions")
    success_rate: float = Field(description="Response success rate 0-100")
    reasoning: str = Field(description="Response coordination reasoning")


SYSTEM_INGEST = """\
You are an expert XDR telemetry analyst.

Given the security telemetry sources:
1. Normalize data from multiple domains
2. Identify high-fidelity signals
3. Establish baseline and anomalies

Prioritize detection accuracy over volume."""

SYSTEM_RESPOND = """\
You are an expert XDR response coordinator.

Given the attack story and context:
1. Select appropriate response actions
2. Coordinate across security domains
3. Validate containment effectiveness

Minimize impact while maximizing containment."""
