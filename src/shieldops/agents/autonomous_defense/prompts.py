"""LLM prompt templates and response schemas for the AutonomousDefense Agent."""

from pydantic import BaseModel, Field


class ThreatOutput(BaseModel):
    """Structured output for threatoutput."""

    threat_count: int = Field(description="Number of threats assessed")
    severity_score: float = Field(description="Overall severity 0-100")


class DefenseOutput(BaseModel):
    """Structured output for defenseoutput."""

    actions_count: int = Field(description="Number of defense actions")
    protection_rate: float = Field(description="Protection effectiveness 0-100")
    reasoning: str = Field(description="Defense reasoning")


SYSTEM_ASSESS = """\
You are an expert threat assessment analyst.

Given the threat landscape data:
1. Assess threats across all vectors
2. Prioritize by severity and likelihood
3. Map threats to defense capabilities

Focus on actionable threat intelligence."""

SYSTEM_DEFEND = """\
You are an expert autonomous defense coordinator.

Given the threat assessment and context:
1. Select optimal countermeasures
2. Deploy defenses autonomously
3. Validate protection effectiveness

Maximize protection while minimizing disruption."""
