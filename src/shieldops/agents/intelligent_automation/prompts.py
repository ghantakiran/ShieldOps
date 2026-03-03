"""LLM prompt templates and response schemas for the IntelligentAutomation Agent."""

from pydantic import BaseModel, Field


class AssessOutput(BaseModel):
    """Structured output for assess_output."""

    severity: str = Field(description="Situation severity: critical/high/medium/low")
    confidence: float = Field(description="Assessment confidence 0-100")


class ExecuteOutput(BaseModel):
    """Structured output for execute_output."""

    actions_count: int = Field(description="Number of actions executed")
    success_rate: float = Field(description="Execution success rate 0-100")
    reasoning: str = Field(description="Execution reasoning")


SYSTEM_ASSESS = """\
You are an expert operational automation analyst.

Given the operational context:
1. Assess the current situation severity
2. Identify automation opportunities
3. Evaluate risk and blast radius

Prioritize safety and reliability."""

SYSTEM_EXECUTE = """\
You are an expert automation executor.

Given the selected strategy:
1. Execute automation actions safely
2. Validate each step before proceeding
3. Maintain rollback capability

Balance speed with safety."""
